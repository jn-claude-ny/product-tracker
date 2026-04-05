import ast
import base64
import json
import logging
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

import redis

from app.config import Config
from celery_app.celery import celery

logger = logging.getLogger(__name__)

# Singleton Redis client for connection pooling
_redis_client: Optional[redis.Redis] = None


def _get_redis_client() -> Optional[redis.Redis]:
    """Get or create singleton Redis client with connection pooling."""
    global _redis_client
    if _redis_client is None:
        try:
            _redis_client = redis.from_url(Config.CELERY_BROKER_URL, decode_responses=True)
        except Exception as exc:
            logger.warning('Failed to create Redis client: %s', exc)
            return None
    return _redis_client


TRACKED_TASK_NAMES = {
    'celery_app.tasks.crawl_tasks.crawl_website',
    'celery_app.tasks.scrape_tasks.scrape_product_batch',
    'celery_app.tasks.discovery_tasks.discover_products_task',
    'celery_app.tasks.discovery_tasks.extract_product_details_batch',
}

TRACKED_QUEUE_NAMES = ('crawl_queue', 'scrape_queue')


class CrawlStateService:
    @staticmethod
    def get_crawl_activity_map(website_ids: Iterable[int]) -> Dict[int, Dict[str, Any]]:
        normalized_ids = {
            CrawlStateService._coerce_int(website_id)
            for website_id in website_ids
        }
        normalized_ids.discard(None)

        activity = {
            website_id: {
                'is_crawling': False,
                'active_task_count': 0,
                'queued_task_count': 0,
                'task_ids': [],
            }
            for website_id in normalized_ids
        }

        if not activity:
            return {}

        for task in CrawlStateService._collect_live_tasks():
            website_id = CrawlStateService._extract_website_id_from_task_payload(task)
            if website_id not in activity:
                continue

            activity[website_id]['is_crawling'] = True
            activity[website_id]['active_task_count'] += 1

            task_id = task.get('id')
            if task_id:
                activity[website_id]['task_ids'].append(task_id)

        for queue_name, message in CrawlStateService._collect_queued_messages(TRACKED_QUEUE_NAMES):
            website_id = CrawlStateService._extract_website_id_from_queue_message(message)
            if website_id not in activity:
                continue

            activity[website_id]['is_crawling'] = True
            activity[website_id]['queued_task_count'] += 1

            task_id = CrawlStateService._extract_queue_task_id(message)
            if task_id:
                activity[website_id]['task_ids'].append(task_id)

        for website_id in activity:
            activity[website_id]['task_ids'] = sorted(set(activity[website_id]['task_ids']))

        return activity

    @staticmethod
    def is_website_currently_crawling(website_id: int) -> bool:
        activity = CrawlStateService.get_crawl_activity_map([website_id]).get(int(website_id), {})
        return bool(activity.get('is_crawling'))

    @staticmethod
    def stop_website_crawl(website_id: int) -> Dict[str, Any]:
        website_id = int(website_id)
        task_ids_to_revoke: Set[str] = set()

        for task in CrawlStateService._collect_live_tasks():
            task_website_id = CrawlStateService._extract_website_id_from_task_payload(task)
            if task_website_id != website_id:
                continue

            task_id = task.get('id')
            if task_id:
                task_ids_to_revoke.add(task_id)

        removed_count, removed_task_ids = CrawlStateService._remove_queued_tasks_for_website(
            website_id,
            TRACKED_QUEUE_NAMES,
        )
        task_ids_to_revoke.update(removed_task_ids)

        revoked_count = 0
        for task_id in sorted(task_ids_to_revoke):
            try:
                celery.control.revoke(task_id, terminate=True, signal='SIGKILL')
                revoked_count += 1
            except Exception as exc:
                logger.warning('Failed to revoke task %s: %s', task_id, exc)

        return {
            'revoked_count': revoked_count,
            'removed_queued_count': removed_count,
            'task_ids': sorted(task_ids_to_revoke),
        }

    @staticmethod
    def _collect_live_tasks() -> List[Dict[str, Any]]:
        collected_tasks: List[Dict[str, Any]] = []

        try:
            inspector = celery.control.inspect(timeout=1.0)
        except Exception as exc:
            logger.warning('Failed to create Celery inspector: %s', exc)
            return collected_tasks

        if not inspector:
            return collected_tasks

        for state_name, getter_name in (
            ('active', 'active'),
            ('reserved', 'reserved'),
            ('scheduled', 'scheduled'),
        ):
            try:
                tasks_by_worker = getattr(inspector, getter_name)() or {}
            except Exception as exc:
                logger.warning('Failed to inspect %s tasks: %s', state_name, exc)
                continue

            for worker_name, tasks in tasks_by_worker.items():
                for task in tasks or []:
                    payload = CrawlStateService._normalize_inspect_task(task)
                    if not payload:
                        continue

                    task_name = payload.get('name')
                    if task_name not in TRACKED_TASK_NAMES:
                        continue

                    payload['_state'] = state_name
                    payload['_worker'] = worker_name
                    collected_tasks.append(payload)

        return collected_tasks

    @staticmethod
    def _normalize_inspect_task(task: Any) -> Dict[str, Any]:
        if not isinstance(task, dict):
            return {}

        if isinstance(task.get('request'), dict):
            payload = dict(task['request'])
        else:
            payload = dict(task)

        return payload

    @staticmethod
    def _collect_queued_messages(queue_names: Iterable[str]) -> List[Tuple[str, Dict[str, Any]]]:
        messages: List[Tuple[str, Dict[str, Any]]] = []

        try:
            redis_client = _get_redis_client()
            if not redis_client:
                return messages
        except Exception as exc:
            logger.warning('Failed to connect to Redis broker: %s', exc)
            return messages

        for queue_name in queue_names:
            try:
                raw_messages = redis_client.lrange(queue_name, 0, -1)
            except Exception as exc:
                logger.warning('Failed to read queue %s: %s', queue_name, exc)
                continue

            for raw_message in raw_messages:
                message = CrawlStateService._decode_queue_message(raw_message)
                if not message:
                    continue

                task_name = message.get('headers', {}).get('task')
                if task_name not in TRACKED_TASK_NAMES:
                    continue

                messages.append((queue_name, message))

        return messages

    @staticmethod
    def _remove_queued_tasks_for_website(website_id: int, queue_names: Iterable[str]) -> Tuple[int, Set[str]]:
        removed_count = 0
        removed_task_ids: Set[str] = set()

        try:
            redis_client = _get_redis_client()
            if not redis_client:
                return removed_count, removed_task_ids
        except Exception as exc:
            logger.warning('Failed to connect to Redis broker for queue removal: %s', exc)
            return removed_count, removed_task_ids

        for queue_name in queue_names:
            try:
                raw_messages = redis_client.lrange(queue_name, 0, -1)
            except Exception as exc:
                logger.warning('Failed to inspect queue %s for removal: %s', queue_name, exc)
                continue

            if not raw_messages:
                continue

            kept_messages: List[bytes] = []
            queue_removed = 0

            for raw_message in raw_messages:
                message = CrawlStateService._decode_queue_message(raw_message)
                if not message:
                    kept_messages.append(raw_message)
                    continue

                task_name = message.get('headers', {}).get('task')
                if task_name not in TRACKED_TASK_NAMES:
                    kept_messages.append(raw_message)
                    continue

                message_website_id = CrawlStateService._extract_website_id_from_queue_message(message)
                if message_website_id != website_id:
                    kept_messages.append(raw_message)
                    continue

                queue_removed += 1
                task_id = CrawlStateService._extract_queue_task_id(message)
                if task_id:
                    removed_task_ids.add(task_id)

            if queue_removed == 0:
                continue

            pipeline = redis_client.pipeline()
            pipeline.delete(queue_name)
            if kept_messages:
                pipeline.rpush(queue_name, *kept_messages)
            pipeline.execute()

            removed_count += queue_removed
            logger.info('Removed %s queued task(s) from %s for website %s', queue_removed, queue_name, website_id)

        return removed_count, removed_task_ids

    @staticmethod
    def _decode_queue_message(raw_message: Any) -> Dict[str, Any]:
        if raw_message is None:
            return {}

        try:
            return json.loads(raw_message)
        except Exception as exc:
            logger.warning('Failed to decode queue message: %s', exc)
            return {}

    @staticmethod
    def _extract_website_id_from_task_payload(task: Dict[str, Any]) -> Optional[int]:
        args = task.get('args')
        parsed_args = CrawlStateService._normalize_args(args)
        if parsed_args:
            return CrawlStateService._coerce_int(parsed_args[0])

        argsrepr = task.get('argsrepr')
        parsed_args = CrawlStateService._normalize_args(argsrepr)
        if parsed_args:
            return CrawlStateService._coerce_int(parsed_args[0])

        return None

    @staticmethod
    def _extract_website_id_from_queue_message(message: Dict[str, Any]) -> Optional[int]:
        args = CrawlStateService._extract_queue_message_args(message)
        if args:
            return CrawlStateService._coerce_int(args[0])

        headers = message.get('headers', {})
        argsrepr = headers.get('argsrepr')
        parsed_args = CrawlStateService._normalize_args(argsrepr)
        if parsed_args:
            return CrawlStateService._coerce_int(parsed_args[0])

        return None

    @staticmethod
    def _extract_queue_message_args(message: Dict[str, Any]) -> List[Any]:
        encoded_body = message.get('body')
        if not encoded_body:
            return []

        try:
            decoded_body = base64.b64decode(encoded_body)
            body = json.loads(decoded_body.decode('utf-8'))
        except Exception as exc:
            logger.warning('Failed to decode queued task body: %s', exc)
            return []

        if not isinstance(body, list) or not body:
            return []

        args = body[0]
        if isinstance(args, (list, tuple)):
            return list(args)

        return []

    @staticmethod
    def _extract_queue_task_id(message: Dict[str, Any]) -> Optional[str]:
        headers = message.get('headers', {})
        properties = message.get('properties', {})
        return headers.get('id') or properties.get('correlation_id')

    @staticmethod
    def _normalize_args(raw_args: Any) -> List[Any]:
        if isinstance(raw_args, (list, tuple)):
            return list(raw_args)

        if not raw_args or not isinstance(raw_args, str):
            return []

        try:
            parsed = ast.literal_eval(raw_args)
        except Exception:
            return []

        if isinstance(parsed, (list, tuple)):
            return list(parsed)

        return []

    @staticmethod
    def _coerce_int(value: Any) -> Optional[int]:
        if isinstance(value, bool) or value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

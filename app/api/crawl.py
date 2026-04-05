from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.crawl_state_service import CrawlStateService
from app.services.website_service import WebsiteService
from celery_app.tasks.crawl_tasks import crawl_website
from celery_app.celery import celery
from app.extensions import db
from app.models.website import Website
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('crawl', __name__)


@bp.route('/websites/<int:website_id>/crawl', methods=['POST'])
@jwt_required()
def trigger_crawl(website_id):
    user_id = int(get_jwt_identity())
    logger.info(f"START CRAWL REQUEST: website_id={website_id}, user_id={user_id}")

    try:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        logger.info(f"Website found: {website.name}, is_crawling={website.is_crawling}")

        # Refresh from database to get latest state
        db.session.refresh(website)
        logger.info(f"After refresh: is_crawling={website.is_crawling}")
        crawl_activity = CrawlStateService.get_crawl_activity_map([website_id]).get(website_id, {
            'is_crawling': False,
            'active_task_count': 0,
            'queued_task_count': 0,
        })
        logger.info(f"Backend crawl activity for website {website_id}: {crawl_activity}")

        # Check if already crawling based on real backend activity
        if crawl_activity.get('is_crawling'):
            logger.warning(f"Crawl already in progress for website {website_id}")
            return jsonify({
                'error': 'Crawl already in progress',
                'active_task_count': crawl_activity.get('active_task_count', 0),
                'queued_task_count': crawl_activity.get('queued_task_count', 0),
            }), 400

        force_full = request.json.get('force_full_crawl', False) if request.json else False
        logger.info(f"Dispatching crawl task to crawl_queue, force_full={force_full}")

        # Update website state BEFORE dispatching task to prevent race condition
        website.is_crawling = True
        website.crawl_state = 'crawling'
        website.current_task_id = None  # Will be set after task creation
        db.session.commit()
        logger.info(f"Database updated: is_crawling=True, crawl_state=crawling")

        task = crawl_website.apply_async(
            args=[website_id, force_full],
            queue='crawl_queue'
        )
        logger.info(f"Task dispatched: task_id={task.id}")

        # Update with the actual task_id
        website.current_task_id = task.id
        db.session.commit()
        logger.info(f"Database updated: task_id={task.id}")

        return jsonify({
            'status': 'success',
            'task_id': task.id,
            'website_id': website_id
        }), 202

    except ValueError as e:
        logger.error(f"ValueError in trigger_crawl: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in trigger_crawl: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/websites/<int:website_id>/crawl/pause', methods=['POST'])
@jwt_required()
def pause_crawl(website_id):
    user_id = int(get_jwt_identity())
    logger.info(f"PAUSE CRAWL REQUEST: website_id={website_id}, user_id={user_id}")

    try:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        logger.info(f"Website found: {website.name}, current_state={website.crawl_state}")

        # Stop all active and queued tasks for this website
        stop_result = CrawlStateService.stop_website_crawl(website_id)
        logger.info(f"Stopped {stop_result['revoked_count']} active tasks and {stop_result['removed_queued_count']} queued tasks")

        # Revoke current task if exists
        if website.current_task_id:
            try:
                celery.control.revoke(website.current_task_id, terminate=True, signal='SIGKILL')
                logger.info(f"Revoked current task: {website.current_task_id}")
            except Exception as exc:
                logger.warning(f"Failed to revoke current task {website.current_task_id}: {exc}")

        # Update website state to paused
        website.crawl_state = 'paused'
        website.is_crawling = False
        website.current_task_id = None
        db.session.commit()
        logger.info("Database updated: crawl_state=paused, is_crawling=False")

        return jsonify({
            'status': 'success',
            'message': f'Crawl paused - stopped {stop_result["revoked_count"]} tasks, removed {stop_result["removed_queued_count"]} queued',
            'website_id': website_id,
            'crawl_state': 'paused',
            'tasks_stopped': stop_result['revoked_count'],
            'tasks_removed': stop_result['removed_queued_count']
        }), 200

    except ValueError as e:
        logger.error(f"ValueError in pause_crawl: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in pause_crawl: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/websites/<int:website_id>/crawl/resume', methods=['POST'])
@jwt_required()
def resume_crawl(website_id):
    user_id = int(get_jwt_identity())
    logger.info(f"RESUME CRAWL REQUEST: website_id={website_id}, user_id={user_id}")

    try:
        from app.models.product import Product
        from celery_app.tasks.discovery_tasks import extract_product_details_batch
        from celery import group
        
        website = WebsiteService.get_website_by_id(website_id, user_id)
        logger.info(f"Website found: {website.name}, current_state={website.crawl_state}")

        # Find products that haven't been processed yet
        unprocessed_products = Product.query.filter_by(
            website_id=website_id
        ).filter(
            Product.detail_last_fetched == None  # Products without details
        ).all()
        
        logger.info(f"Found {len(unprocessed_products)} unprocessed products")
        
        # Filter out products without valid SKU
        valid_products = [p for p in unprocessed_products if p.sku]
        if len(valid_products) != len(unprocessed_products):
            logger.warning(f"Filtered out {len(unprocessed_products) - len(valid_products)} products without SKU")
        
        if valid_products:
            # Re-queue detail extraction tasks
            product_ids = [p.sku for p in valid_products]
            batch_size = 50
            batches = [product_ids[i:i + batch_size] for i in range(0, len(product_ids), batch_size)]
            
            tasks = [extract_product_details_batch.s(website_id, batch) for batch in batches]
            job = group(tasks)
            job.apply_async(queue='scrape_queue')
            
            logger.info(f"Re-queued {len(batches)} batches for detail extraction")
            
            # Update website state to crawling
            website.crawl_state = 'crawling'
            website.is_crawling = True
            db.session.commit()
            logger.info("Database updated: crawl_state=crawling, is_crawling=True")
            
            return jsonify({
                'status': 'success',
                'message': f'Crawl resumed - queued {len(batches)} batches ({len(unprocessed_products)} products)',
                'website_id': website_id,
                'crawl_state': 'crawling',
                'batches_queued': len(batches),
                'products_remaining': len(unprocessed_products)
            }), 200
        else:
            # No unprocessed products - mark as completed
            website.crawl_state = 'completed'
            website.is_crawling = False
            db.session.commit()
            
            return jsonify({
                'status': 'success',
                'message': 'No products to process - crawl already completed',
                'website_id': website_id,
                'crawl_state': 'completed'
            }), 200

    except ValueError as e:
        logger.error(f"ValueError in resume_crawl: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in resume_crawl: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/websites/<int:website_id>/crawl/stop', methods=['POST'])
@jwt_required()
def stop_crawl(website_id):
    user_id = int(get_jwt_identity())
    logger.info(f"STOP CRAWL REQUEST: website_id={website_id}, user_id={user_id}")

    try:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        logger.info(f"Website found: {website.name}, current_task_id={website.current_task_id}")
        stop_result = CrawlStateService.stop_website_crawl(website_id)

        if website.current_task_id and website.current_task_id not in stop_result['task_ids']:
            try:
                celery.control.revoke(website.current_task_id, terminate=True, signal='SIGKILL')
                stop_result['task_ids'].append(website.current_task_id)
                stop_result['revoked_count'] += 1
                logger.info(f"Revoked stored current task id: {website.current_task_id}")
            except Exception as exc:
                logger.warning(f"Failed to revoke stored current task id {website.current_task_id}: {exc}")

        # Update website state
        website.crawl_state = 'paused'
        website.is_crawling = False
        website.current_task_id = None
        db.session.commit()
        logger.info("Database updated: crawl_state=paused, is_crawling=False, task_id=None")

        return jsonify({
            'status': 'success',
            'message': (
                f"Stopped {stop_result['revoked_count']} task(s) and "
                f"removed {stop_result['removed_queued_count']} queued task(s)"
            ),
            'website_id': website_id,
            'revoked_count': stop_result['revoked_count'],
            'removed_queued_count': stop_result['removed_queued_count'],
        }), 200

    except ValueError as e:
        logger.error(f"ValueError in stop_crawl: {e}")
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        logger.error(f"Unexpected error in stop_crawl: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500


@bp.route('/crawl/purge-all-tasks', methods=['POST'])
@jwt_required()
def purge_all_tasks():
    """Emergency endpoint to purge all tasks and reset all crawl states"""
    user_id = int(get_jwt_identity())
    logger.info(f"PURGE ALL TASKS REQUEST: user_id={user_id}")

    try:
        # Revoke all active tasks
        i = celery.control.inspect()
        revoked_count = 0

        active_tasks = i.active()
        logger.info(f"Active tasks: {active_tasks}")
        if active_tasks:
            for worker, tasks in active_tasks.items():
                for task in tasks:
                    logger.info(f"Revoking task {task['id']} from worker {worker}")
                    celery.control.revoke(task['id'], terminate=True, signal='SIGKILL')
                    revoked_count += 1

        # Purge all queues - need to purge each queue specifically
        logger.info("Purging all queues")
        from kombu import Connection

        # Purge using control API (purges default queue)
        purged = celery.control.purge()
        logger.info(f"Control purge result: {purged}")

        # Manually purge specific queues
        with Connection(celery.conf.broker_url) as conn:
            for queue_name in ['crawl_queue', 'scrape_queue', 'index_queue']:
                try:
                    queue = conn.SimpleQueue(queue_name)
                    purged_count = queue.clear()
                    logger.info(f"Purged {purged_count} tasks from {queue_name}")
                    queue.close()
                except Exception as e:
                    logger.warning(f"Failed to purge {queue_name}: {e}")

        # Reset all websites for this user
        websites = Website.query.filter_by(user_id=user_id).all()
        logger.info(f"Resetting {len(websites)} websites")
        for website in websites:
            website.is_crawling = False
            website.current_task_id = None
            # Clear sitemap cache to force fresh crawl
            website.sitemap_etag = None
            website.sitemap_last_checked = None
        db.session.commit()
        logger.info("All websites reset successfully with sitemap cache cleared")

        return jsonify({
            'status': 'success',
            'message': f'Purged {revoked_count} tasks and reset all crawl states',
            'websites_reset': len(websites)
        }), 200

    except Exception as e:
        logger.error(f"Error in purge_all_tasks: {e}", exc_info=True)
        return jsonify({'error': str(e)}), 500

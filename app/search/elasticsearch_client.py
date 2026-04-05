from elasticsearch import Elasticsearch
from app.config import Config
import logging

logger = logging.getLogger(__name__)


class ElasticsearchClient:
    _instance = None
    _client = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._client is None:
            self._client = Elasticsearch([Config.ELASTICSEARCH_URL])
            self._setup_index()

    @property
    def client(self):
        return self._client

    def _setup_index(self):
        index_name = 'products_current'

        if not self._client.indices.exists(index=index_name):
            mapping = {
                'mappings': {
                    'properties': {
                        'product_id': {'type': 'keyword'},
                        'website_id': {'type': 'keyword'},
                        'user_id': {'type': 'keyword'},
                        'url': {'type': 'keyword'},
                        'title': {
                            'type': 'text',
                            'fields': {
                                'keyword': {'type': 'keyword'}
                            }
                        },
                        'brand': {'type': 'keyword'},
                        'sku': {'type': 'keyword'},
                        'price': {
                            'type': 'scaled_float',
                            'scaling_factor': 100
                        },
                        'currency': {'type': 'keyword'},
                        'availability': {'type': 'keyword'},
                        'categories': {'type': 'keyword'},
                        'image': {'type': 'keyword'},
                        'created_at': {'type': 'date'},
                        'updated_at': {'type': 'date'}
                    }
                },
                'settings': {
                    'number_of_shards': 1,
                    'number_of_replicas': 0
                }
            }

            self._client.indices.create(index=index_name, body=mapping)
            logger.info(f'Created Elasticsearch index: {index_name}')

        self._setup_ilm_policy()

    def _setup_ilm_policy(self):
        policy_name = 'products_policy'

        try:
            self._client.ilm.get_lifecycle(policy=policy_name)
            logger.info(f'ILM policy {policy_name} already exists')
        except Exception:
            policy = {
                'policy': {
                    'phases': {
                        'hot': {
                            'actions': {
                                'rollover': {
                                    'max_age': '30d',
                                    'max_size': '50gb'
                                }
                            }
                        },
                        'delete': {
                            'min_age': '90d',
                            'actions': {
                                'delete': {}
                            }
                        }
                    }
                }
            }

            try:
                self._client.ilm.put_lifecycle(policy=policy_name, body=policy)
                logger.info(f'Created ILM policy: {policy_name}')
            except Exception as e:
                logger.warning(f'Failed to create ILM policy: {e}')

    def index_product(self, product_id: int, data: dict):
        index_name = 'products_current'

        try:
            self._client.index(
                index=index_name,
                id=f'product_{product_id}',
                body=data
            )
            logger.debug(f'Indexed product {product_id}')
        except Exception as e:
            logger.error(f'Failed to index product {product_id}: {e}')
            raise

    def search_products(self, query: str, filters: dict = None,
                        user_id: int = None, page: int = 1, page_size: int = 20):
        index_name = 'products_current'

        must_clauses = []

        if query:
            must_clauses.append({
                'multi_match': {
                    'query': query,
                    'fields': ['title^3', 'brand^2', 'sku'],
                    'fuzziness': 'AUTO'
                }
            })

        if user_id:
            must_clauses.append({
                'term': {'user_id': str(user_id)}
            })

        filter_clauses = []

        if filters:
            if 'website_id' in filters:
                filter_clauses.append({
                    'term': {'website_id': str(filters['website_id'])}
                })

            if 'brand' in filters:
                filter_clauses.append({
                    'term': {'brand': filters['brand']}
                })

            if 'min_price' in filters:
                filter_clauses.append({
                    'range': {'price': {'gte': filters['min_price']}}
                })

            if 'max_price' in filters:
                filter_clauses.append({
                    'range': {'price': {'lte': filters['max_price']}}
                })

            if 'availability' in filters:
                filter_clauses.append({
                    'term': {'availability': filters['availability']}
                })

            if 'categories' in filters:
                filter_clauses.append({
                    'terms': {'categories': filters['categories']}
                })

        search_body = {
            'query': {
                'bool': {
                    'must': must_clauses if must_clauses else [{'match_all': {}}],
                    'filter': filter_clauses
                }
            },
            'from': (page - 1) * page_size,
            'size': page_size,
            'sort': [
                {'updated_at': {'order': 'desc'}}
            ]
        }

        try:
            response = self._client.search(index=index_name, body=search_body)

            hits = response['hits']['hits']
            total = response['hits']['total']['value']

            results = []
            for hit in hits:
                result = hit['_source']
                result['score'] = hit['_score']
                results.append(result)

            return {
                'results': results,
                'total': total,
                'page': page,
                'page_size': page_size,
                'total_pages': (total + page_size - 1) // page_size
            }

        except Exception as e:
            logger.error(f'Search error: {e}')
            raise

    def delete_product(self, product_id: int):
        index_name = 'products_current'

        try:
            self._client.delete(index=index_name, id=f'product_{product_id}')
            logger.debug(f'Deleted product {product_id} from index')
        except Exception as e:
            logger.warning(f'Failed to delete product {product_id}: {e}')

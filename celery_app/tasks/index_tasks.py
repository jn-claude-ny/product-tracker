from celery_app.celery import celery
import logging
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.models.website import Website
from app.search.elasticsearch_client import ElasticsearchClient

logger = logging.getLogger(__name__)


@celery.task(bind=True, max_retries=3)
def index_product(self, product_id):
    logger.info(f'Indexing product {product_id}')
    
    try:
        from app import create_app
        app = create_app()
        
        with app.app_context():
            product = Product.query.get(product_id)
            if not product:
                logger.error(f'Product {product_id} not found')
                return {'status': 'error', 'message': 'Product not found'}
            
            website = Website.query.get(product.website_id)
            
            latest_snapshot = ProductSnapshot.query.filter_by(
                product_id=product_id
            ).order_by(ProductSnapshot.created_at.desc()).first()
            
            document = {
                'product_id': product.id,
                'website_id': product.website_id,
                'user_id': website.user_id,
                'url': product.url,
                'title': product.title,
                'brand': product.brand,
                'sku': product.sku,
                'categories': product.categories or [],
                'image': product.image,
                'created_at': product.created_at.isoformat(),
                'updated_at': product.updated_at.isoformat()
            }
            
            if latest_snapshot:
                document['price'] = float(latest_snapshot.price) if latest_snapshot.price else None
                document['currency'] = latest_snapshot.currency
                document['availability'] = latest_snapshot.availability
            
            es_client = ElasticsearchClient()
            es_client.index_product(product_id, document)
            
            return {'status': 'success', 'product_id': product_id}
            
    except Exception as e:
        logger.error(f'Error indexing product: {e}')
        raise

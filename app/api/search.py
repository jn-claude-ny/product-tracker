from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import or_
from app.search.elasticsearch_client import ElasticsearchClient
import logging

logger = logging.getLogger(__name__)

bp = Blueprint('search', __name__)


def _get_status_badge(availability):
    """Compute status badge from availability text"""
    if not availability:
        return None
    a = availability.lower()
    if 'sale' in a or 'discount' in a or 'off' in a:
        return 'SALE'
    if 'new' in a:
        return 'NEW'
    if 'clearance' in a:
        return 'CLEARANCE'
    if 'limited' in a:
        return 'LIMITED'
    if 'back in stock' in a or 'back-in-stock' in a:
        return 'BACK'
    if 'out of stock' in a or 'unavailable' in a or a == 'false' or a == '0':
        return 'OUT'
    if 'in stock' in a or 'instock' in a or a == 'true' or a == '1':
        return None
    return None


@bp.route('', methods=['GET'])
@jwt_required()
def search_products():
    user_id = int(get_jwt_identity())
    logger.info(f"Search request from user {user_id}")

    query = request.args.get('q', '')
    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 20))
    sort_by = request.args.get('sort', 'modified_desc')

    filters = {}

    if request.args.get('website_id'):
        filters['website_id'] = int(request.args.get('website_id'))

    if request.args.get('brand'):
        filters['brand'] = request.args.get('brand')

    if request.args.get('min_price'):
        filters['min_price'] = float(request.args.get('min_price'))

    if request.args.get('max_price'):
        filters['max_price'] = float(request.args.get('max_price'))

    if request.args.get('availability'):
        filters['availability'] = request.args.get('availability')

    if request.args.get('categories'):
        filters['categories'] = request.args.get('categories').split(',')

    try:
        logger.info(f"Attempting Elasticsearch search: query='{query}', filters={filters}")
        es_client = ElasticsearchClient()
        results = es_client.search_products(
            query=query,
            filters=filters,
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        logger.info(f"Elasticsearch returned {len(results.get('results', []))} results")

        # Force fallback if no results from ES
        if not results.get('results'):
            logger.warning("Elasticsearch returned empty results, forcing database fallback")
            raise Exception("Empty results from Elasticsearch")

        return jsonify(results), 200

    except Exception as e:
        logger.error(f"Elasticsearch failed: {e}, using database fallback")
        # Fallback to database search if Elasticsearch fails
        from app.models.product import Product
        from app.models.website import Website
        from app.models.product_snapshot import ProductSnapshot

        # Build query
        logger.info(f"Building database query for user {user_id}")
        query_obj = Product.query.join(Website).filter(Website.user_id == user_id)

        # Apply search filter
        if query:
            query_obj = query_obj.filter(
                or_(
                    Product.title.ilike(f'%{query}%'),
                    Product.brand.ilike(f'%{query}%'),
                    Product.sku.ilike(f'%{query}%')
                )
            )

        # Apply filters
        if filters.get('website_id'):
            query_obj = query_obj.filter(Product.website_id == filters['website_id'])

        if filters.get('brand'):
            query_obj = query_obj.filter(Product.brand.ilike(f'%{filters["brand"]}%'))

        # Get total count
        total = query_obj.count()
        logger.info(f"Database query found {total} total products")

        # Calculate offset for pagination
        offset = (page - 1) * page_size

        # Apply sorting
        if sort_by == 'price_asc':
            # Sort by price after getting results (simpler approach)
            products = query_obj.offset(offset).limit(page_size).all()
            # Sort in memory by latest price
            products_with_price = []
            for product in products:
                latest_snapshot = ProductSnapshot.query.filter_by(
                    product_id=product.id
                ).order_by(ProductSnapshot.created_at.desc()).first()
                price = float(latest_snapshot.price) if latest_snapshot and latest_snapshot.price else None
                products_with_price.append((product, price))

            products_with_price.sort(key=lambda x: (x[1] is None, x[1]))
            products = [p[0] for p in products_with_price]
        elif sort_by == 'price_desc':
            # Sort by price after getting results (simpler approach)
            products = query_obj.offset(offset).limit(page_size).all()
            # Sort in memory by latest price
            products_with_price = []
            for product in products:
                latest_snapshot = ProductSnapshot.query.filter_by(
                    product_id=product.id
                ).order_by(ProductSnapshot.created_at.desc()).first()
                price = float(latest_snapshot.price) if latest_snapshot and latest_snapshot.price else None
                products_with_price.append((product, price))

            products_with_price.sort(key=lambda x: (x[1] is not None, -x[1] if x[1] is not None else 0))
            products = [p[0] for p in products_with_price]
        elif sort_by == 'title_asc':
            query_obj = query_obj.order_by(Product.title.asc())
            products = query_obj.offset(offset).limit(page_size).all()
        elif sort_by == 'created_desc':
            query_obj = query_obj.order_by(Product.created_at.desc())
            products = query_obj.offset(offset).limit(page_size).all()
        else:  # modified_desc (default)
            query_obj = query_obj.order_by(Product.updated_at.desc())
            products = query_obj.offset(offset).limit(page_size).all()

        logger.info(f"Returning {len(products)} products for page {page}")

        # Format results
        results_list = []
        for product in products:
            latest_snapshot = ProductSnapshot.query.filter_by(
                product_id=product.id
            ).order_by(ProductSnapshot.created_at.desc()).first()

            availability = latest_snapshot.availability if latest_snapshot else None
            status_badge = _get_status_badge(availability)

            results_list.append({
                'product_id': product.id,
                'title': product.title,
                'brand': product.brand,
                'url': product.url,
                'image': product.image,
                'price': float(latest_snapshot.price) if latest_snapshot and latest_snapshot.price else None,
                'currency': latest_snapshot.currency if latest_snapshot else 'USD',
                'availability': availability,
                'status_badge': status_badge,
                'website_id': product.website_id,
                'updated_at': product.updated_at.isoformat()
            })

        logger.info(f"Database fallback returning {len(results_list)} formatted results")
        return jsonify({
            'results': results_list,
            'total': total,
            'page': page,
            'pages': (total + page_size - 1) // page_size,
            'page_size': page_size
        }), 200

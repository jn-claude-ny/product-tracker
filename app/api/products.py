from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.product import Product
from app.models.website import Website
from app.extensions import db
from sqlalchemy import or_, and_

bp = Blueprint('products', __name__)


def _parse_bool_param(value):
    """Parse boolean query parameter correctly."""
    if value is None:
        return None
    return value.lower() in ('true', '1', 'yes', 'on')


@bp.route('', methods=['GET'])
@jwt_required()
def get_products():
    """Get all products from user's websites with filtering"""
    user_id = int(get_jwt_identity())
    
    # Get query parameters
    website_id = request.args.get('website_id', type=int)
    gender = request.args.get('gender')
    search = request.args.get('search', '')
    availability = request.args.get('availability')
    is_new = _parse_bool_param(request.args.get('is_new'))
    is_on_sale = _parse_bool_param(request.args.get('is_on_sale'))
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort_by = request.args.get('sort_by', 'updated_at')
    sort_order = request.args.get('sort_order', 'desc')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)
    
    # Base query - join with websites to filter by user
    query = Product.query.join(Website).filter(Website.user_id == user_id)
    
    # Apply filters
    if website_id:
        query = query.filter(Product.website_id == website_id)
    
    if gender:
        query = query.filter(Product.gender == gender)
    
    if search:
        search_term = f'%{search}%'
        query = query.filter(
            or_(
                Product.title.ilike(search_term),
                Product.brand.ilike(search_term),
                Product.sku.ilike(search_term)
            )
        )
    
    if is_new is not None:
        query = query.filter(Product.is_new == is_new)
    
    if is_on_sale is not None:
        query = query.filter(Product.is_on_sale == is_on_sale)
    
    if min_price is not None:
        query = query.filter(Product.price_current >= min_price)
    
    if max_price is not None:
        query = query.filter(Product.price_current <= max_price)
    
    # Sorting
    sort_column = getattr(Product, sort_by, Product.updated_at)
    if sort_order == 'desc':
        query = query.order_by(db.desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Pagination
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format response
    products = []
    for product in paginated.items:
        products.append({
            'id': product.id,
            'website_id': product.website_id,
            'url': product.url,
            'sku': product.sku,
            'title': product.title,
            'brand': product.brand,
            'image': product.image,
            'gender': product.gender,
            'category': product.category,
            'color': product.color,
            'price_current': float(product.price_current) if product.price_current else None,
            'price_previous': float(product.price_previous) if product.price_previous else None,
            'currency': product.currency,
            'is_new': product.is_new,
            'is_on_sale': product.is_on_sale,
            'availability': product.availability,
            'available': product.available,
            'inventory_level': product.inventory_level,
            'created_at': product.created_at.isoformat() if product.created_at else None,
            'updated_at': product.updated_at.isoformat() if product.updated_at else None,
        })
    
    return jsonify({
        'products': products,
        'total': paginated.total,
        'page': paginated.page,
        'per_page': paginated.per_page,
        'pages': paginated.pages
    }), 200


@bp.route('/<int:product_id>', methods=['GET'])
@jwt_required()
def get_product(product_id):
    """Get single product details"""
    user_id = int(get_jwt_identity())
    
    product = Product.query.join(Website).filter(
        Product.id == product_id,
        Website.user_id == user_id
    ).first()
    
    if not product:
        return jsonify({'error': 'Product not found'}), 404
    
    # Get variants if they exist
    variants = []
    try:
        if product.variants.count() > 0:
            for variant in product.variants:
                variants.append(variant.to_dict())
    except Exception:
        pass  # No variants or error accessing them
    
    return jsonify({
        'id': product.id,
        'website_id': product.website_id,
        'url': product.url,
        'sku': product.sku,
        'title': product.title,
        'brand': product.brand,
        'image': product.image,
        'gender': product.gender,
        'category': product.category,
        'color': product.color,
        'price_current': float(product.price_current) if product.price_current else None,
        'price_previous': float(product.price_previous) if product.price_previous else None,
        'currency': product.currency,
        'is_new': product.is_new,
        'is_on_sale': product.is_on_sale,
        'availability': product.availability,
        'available': product.available,
        'inventory_level': product.inventory_level,
        'variants': variants,
        'created_at': product.created_at.isoformat() if product.created_at else None,
        'updated_at': product.updated_at.isoformat() if product.updated_at else None,
    }), 200

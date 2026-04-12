from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import Schema, fields, ValidationError
from app.models.tracked_product import TrackedProduct
from app.models.product import Product
from app.extensions import db

bp = Blueprint('tracked_products', __name__)


class TrackedProductSchema(Schema):
    id = fields.Int(dump_only=True)
    product_id = fields.Int(required=True)
    priority = fields.Str(validate=lambda x: x in ['now', 'urgent', 'high', 'moderate', 'normal'])
    crawl_period_hours = fields.Int(validate=lambda x: x >= 1, allow_none=True)
    schedule = fields.Str(validate=lambda x: x in ['hourly', 'every_6_hours', 'every_12_hours', 'daily', 'weekly'], allow_none=True)
    # New price direction tracking
    price_direction = fields.Str(validate=lambda x: x in ['above', 'below'], allow_none=True)
    price_reference = fields.Decimal(places=2, allow_none=True)
    # Legacy price tracking
    price_condition = fields.Str(validate=lambda x: x in ['greater_than', 'less_than', 'equal_to'], allow_none=True)
    price_threshold = fields.Decimal(places=2, allow_none=True)
    size_filter = fields.List(fields.Str(), allow_none=True)
    availability_filter = fields.Str(allow_none=True)
    discord_webhook_url = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)

    # Include product details + variants
    product = fields.Method('get_product_details', dump_only=True)

    def get_product_details(self, obj):
        if obj.product:
            from app.models.product_snapshot import ProductSnapshot
            latest_snapshot = ProductSnapshot.query.filter_by(product_id=obj.product.id).order_by(db.desc('created_at')).first()
            latest_price = float(latest_snapshot.price) if latest_snapshot and latest_snapshot.price else None

            variants = []
            try:
                if obj.product.variants.count() > 0:
                    for v in obj.product.variants:
                        variants.append({
                            'id': v.id,
                            'variant_sku': v.variant_sku,
                            'size': v.size,
                            'color': v.color,
                            'price': float(v.price) if v.price else None,
                            'available': v.available,
                            'stock_state': v.stock_state,
                            'inventory_level': v.inventory_level,
                            'last_checked': v.last_checked.isoformat() if v.last_checked else None,
                        })
            except Exception:
                pass

            return {
                'id': obj.product.id,
                'title': obj.product.title,
                'url': obj.product.url,
                'image': obj.product.image,
                'price': latest_price,
                'price_current': float(obj.product.price_current) if obj.product.price_current else None,
                'availability': obj.product.availability,
                'available': obj.product.available,
                'brand': obj.product.brand,
                'sku': obj.product.sku,
                'variants': variants
            }
        return None


@bp.route('', methods=['GET'])
@jwt_required()
def get_tracked_products():
    user_id = int(get_jwt_identity())
    tracked_products = TrackedProduct.query.filter_by(user_id=user_id).order_by(TrackedProduct.created_at.desc()).all()

    schema = TrackedProductSchema(many=True)
    return jsonify(schema.dump(tracked_products)), 200


@bp.route('', methods=['POST'])
@jwt_required()
def create_tracked_product():
    user_id = int(get_jwt_identity())

    try:
        schema = TrackedProductSchema()
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400

    # Verify product exists and belongs to user
    from app.models.website import Website
    product = Product.query.join(Website).filter(
        Product.id == data['product_id'],
        Website.user_id == user_id
    ).first()

    if not product:
        return jsonify({'error': 'Product not found'}), 404

    # Check if already tracking
    existing = TrackedProduct.query.filter_by(
        user_id=user_id,
        product_id=data['product_id']
    ).first()

    if existing:
        return jsonify({'error': 'Product already being tracked'}), 400

    # Set price reference if price_direction is provided
    if data.get('price_direction') and product.price_current:
        data['price_reference'] = float(product.price_current)

    # Normalise crawl_period_hours from human-readable schedule keys
    schedule_map = {'hourly': 1, 'every_6_hours': 6, 'every_12_hours': 12, 'daily': 24, 'weekly': 168}
    schedule_key = request.json.get('schedule')
    if schedule_key and schedule_key in schedule_map:
        data['crawl_period_hours'] = schedule_map[schedule_key]

    # Create tracked product
    tracked_product = TrackedProduct(
        user_id=user_id,
        **data
    )

    db.session.add(tracked_product)
    db.session.commit()

    # Trigger immediate check if priority is 'now' or 'urgent'
    priority = data.get('priority', 'normal')
    if priority in ['now', 'urgent']:
        from celery_app.tasks.tracked_product_tasks import trigger_tracked_product_now
        result = trigger_tracked_product_now.delay(tracked_product.id)
        print(f"[TRACK] Triggered immediate check for tracked product {tracked_product.id}, task: {result.id}")

    response_schema = TrackedProductSchema()
    return jsonify(response_schema.dump(tracked_product)), 201


@bp.route('/<int:tracked_product_id>', methods=['PUT'])
@jwt_required()
def update_tracked_product(tracked_product_id):
    user_id = int(get_jwt_identity())

    tracked_product = TrackedProduct.query.filter_by(
        id=tracked_product_id,
        user_id=user_id
    ).first()

    if not tracked_product:
        return jsonify({'error': 'Tracked product not found'}), 404

    try:
        schema = TrackedProductSchema(partial=True)
        data = schema.load(request.json)
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400

    # Update fields
    for key, value in data.items():
        if hasattr(tracked_product, key):
            setattr(tracked_product, key, value)

    db.session.commit()

    response_schema = TrackedProductSchema()
    return jsonify(response_schema.dump(tracked_product)), 200


@bp.route('/<int:tracked_product_id>/run', methods=['POST'])
@jwt_required()
def run_tracked_product_now(tracked_product_id):
    """Manually trigger an immediate check for a tracked product."""
    user_id = int(get_jwt_identity())

    tracked_product = TrackedProduct.query.filter_by(
        id=tracked_product_id,
        user_id=user_id
    ).first()

    if not tracked_product:
        return jsonify({'error': 'Tracked product not found'}), 404

    try:
        from celery_app.tasks.tracked_product_tasks import trigger_tracked_product_now
        result = trigger_tracked_product_now.delay(tracked_product.id)
        return jsonify({
            'success': True,
            'task_id': result.id,
            'tracked_product_id': tracked_product_id
        }), 202
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@bp.route('/<int:tracked_product_id>', methods=['DELETE'])
@jwt_required()
def delete_tracked_product(tracked_product_id):
    user_id = int(get_jwt_identity())

    tracked_product = TrackedProduct.query.filter_by(
        id=tracked_product_id,
        user_id=user_id
    ).first()

    if not tracked_product:
        return jsonify({'error': 'Tracked product not found'}), 404

    db.session.delete(tracked_product)
    db.session.commit()

    return '', 204

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models.alert import Alert
from app.models.product import Product
from app.models.product_snapshot import ProductSnapshot
from app.schemas.alert import AlertSchema

bp = Blueprint('alerts', __name__)


@bp.route('', methods=['GET'])
@jwt_required()
def get_alerts():
    user_id = int(get_jwt_identity())

    page = int(request.args.get('page', 1))
    page_size = int(request.args.get('page_size', 50))

    query = Alert.query.filter_by(user_id=user_id)

    if request.args.get('alert_type'):
        query = query.filter_by(alert_type=request.args.get('alert_type'))

    if request.args.get('product_id'):
        query = query.filter_by(product_id=int(request.args.get('product_id')))

    query = query.order_by(Alert.sent_at.desc())

    paginated = query.paginate(page=page, per_page=page_size, error_out=False)

    schema = AlertSchema(many=True)
    alerts_data = schema.dump(paginated.items)

    for alert_data in alerts_data:
        alert = next(a for a in paginated.items if a.id == alert_data['id'])
        product = Product.query.get(alert.product_id)

        if product:
            alert_data['product'] = {
                'id': product.id,
                'title': product.title,
                'url': product.url,
                'image': product.image,
                'brand': product.brand
            }

            latest_snapshot = ProductSnapshot.query.filter_by(
                product_id=product.id
            ).order_by(ProductSnapshot.created_at.desc()).first()

            if latest_snapshot:
                alert_data['product']['price'] = str(latest_snapshot.price) if latest_snapshot.price else None
                alert_data['product']['currency'] = latest_snapshot.currency
                alert_data['product']['availability'] = latest_snapshot.availability

    return jsonify({
        'alerts': alerts_data,
        'total': paginated.total,
        'page': page,
        'page_size': page_size,
        'total_pages': paginated.pages
    }), 200

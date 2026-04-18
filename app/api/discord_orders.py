"""
Dashboard API: Discord orders with Discord user info.
GET  /api/discord-orders           – list all orders (admin)
GET  /api/discord-orders/<id>      – single order detail
PUT  /api/discord-orders/<id>/cancel   – cancel an order
DELETE /api/discord-orders/<id>    – delete record
"""
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from sqlalchemy import select, desc

from app.extensions import db
from app.models.discord_order import DiscordOrder
from app.models.user_discord_link import UserDiscordLink
from app.models.user import User
from app.models.product import Product

bp = Blueprint('discord_orders', __name__)


def _order_to_dict(order: DiscordOrder) -> dict:
    discord_link = UserDiscordLink.query.filter_by(user_id=order.user_id).first()
    product = order.product

    return {
        'id': order.id,
        'discord_user_id': order.discord_user_id,
        'discord_name': discord_link.discord_name if discord_link else None,
        'discord_avatar_url': discord_link.discord_avatar_url if discord_link else None,
        'user_id': order.user_id,
        'product_id': order.product_id,
        'product_title': product.title if product else None,
        'product_brand': product.brand if product else None,
        'product_image': product.image if product else None,
        'product_url': product.url if product else None,
        'alert_type': order.alert_type,
        'size_filter': order.size_filter,
        'status': order.status,
        'last_alert_at': order.last_alert_at.isoformat() if order.last_alert_at else None,
        'created_at': order.created_at.isoformat(),
        'updated_at': order.updated_at.isoformat(),
    }


@bp.route('', methods=['GET'])
@jwt_required()
def list_discord_orders():
    """Admin endpoint: list all discord orders with filters."""
    status_filter = request.args.get('status')
    discord_user_id = request.args.get('discord_user_id')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 50, type=int)

    query = DiscordOrder.query

    if status_filter:
        query = query.filter(DiscordOrder.status == status_filter)
    if discord_user_id:
        query = query.filter(DiscordOrder.discord_user_id == discord_user_id)

    query = query.order_by(desc(DiscordOrder.created_at))
    paginated = query.paginate(page=page, per_page=per_page, error_out=False)

    return jsonify({
        'orders': [_order_to_dict(o) for o in paginated.items],
        'total': paginated.total,
        'page': paginated.page,
        'per_page': paginated.per_page,
        'pages': paginated.pages,
    }), 200


@bp.route('/<int:order_id>', methods=['GET'])
@jwt_required()
def get_discord_order(order_id):
    order = DiscordOrder.query.get_or_404(order_id)
    return jsonify(_order_to_dict(order)), 200


@bp.route('/<int:order_id>/cancel', methods=['PUT'])
@jwt_required()
def cancel_discord_order(order_id):
    order = DiscordOrder.query.get_or_404(order_id)
    if order.status != 'active':
        return jsonify({'error': 'Order is not active'}), 400

    order.status = 'cancelled'
    db.session.commit()
    return jsonify(_order_to_dict(order)), 200


@bp.route('/<int:order_id>', methods=['DELETE'])
@jwt_required()
def delete_discord_order(order_id):
    order = DiscordOrder.query.get_or_404(order_id)
    db.session.delete(order)
    db.session.commit()
    return '', 204

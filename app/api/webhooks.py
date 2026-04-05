from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.extensions import db
from app.models.discord_webhook import DiscordWebhook
from app.models.website import Website
from app.schemas.discord_webhook import DiscordWebhookSchema, DiscordWebhookCreateSchema

bp = Blueprint('webhooks', __name__)


@bp.route('/websites/<int:website_id>/webhooks', methods=['GET'])
@jwt_required()
def get_webhooks(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    webhooks = DiscordWebhook.query.filter_by(website_id=website_id).all()

    schema = DiscordWebhookSchema(many=True)
    return jsonify(schema.dump(webhooks)), 200


@bp.route('/websites/<int:website_id>/webhooks', methods=['POST'])
@jwt_required()
def create_webhook(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    try:
        schema = DiscordWebhookCreateSchema()
        data = schema.load(request.json)

        webhook = DiscordWebhook(website_id=website_id, **data)
        db.session.add(webhook)
        db.session.commit()

        response_schema = DiscordWebhookSchema()
        return jsonify(response_schema.dump(webhook)), 201

    except ValidationError as e:
        return jsonify({'error': e.messages}), 400


@bp.route('/webhooks/<int:webhook_id>', methods=['DELETE'])
@jwt_required()
def delete_webhook(webhook_id):
    user_id = int(get_jwt_identity())

    webhook = DiscordWebhook.query.join(Website).filter(
        DiscordWebhook.id == webhook_id,
        Website.user_id == user_id
    ).first()

    if not webhook:
        return jsonify({'error': 'Webhook not found'}), 404

    db.session.delete(webhook)
    db.session.commit()

    return '', 204

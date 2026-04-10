from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.services.crawl_state_service import CrawlStateService
from app.services.website_service import WebsiteService
from app.schemas.website import WebsiteSchema, WebsiteCreateSchema, WebsiteUpdateSchema

bp = Blueprint('websites', __name__)


@bp.route('', methods=['GET'])
@jwt_required()
def get_websites():
    user_id = int(get_jwt_identity())
    websites = WebsiteService.get_user_websites(user_id)
    crawl_activity = CrawlStateService.get_crawl_activity_map([website.id for website in websites])

    for website in websites:
        website._crawl_activity = crawl_activity.get(website.id, {
            'is_crawling': False,
            'active_task_count': 0,
            'queued_task_count': 0,
        })

    schema = WebsiteSchema(many=True)
    return jsonify(schema.dump(websites)), 200


@bp.route('/<int:website_id>', methods=['GET'])
@jwt_required()
def get_website(website_id):
    user_id = int(get_jwt_identity())
    try:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        website._crawl_activity = CrawlStateService.get_crawl_activity_map([website.id]).get(website.id, {
            'is_crawling': False,
            'active_task_count': 0,
            'queued_task_count': 0,
        })
        schema = WebsiteSchema()
        return jsonify(schema.dump(website)), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@bp.route('', methods=['POST'])
@jwt_required()
def create_website():
    user_id = int(get_jwt_identity())
    try:
        schema = WebsiteCreateSchema()
        data = schema.load(request.json)

        website = WebsiteService.create_website(user_id, **data)

        response_schema = WebsiteSchema()
        return jsonify(response_schema.dump(website)), 201
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400


@bp.route('/<int:website_id>', methods=['PUT'])
@jwt_required()
def update_website(website_id):
    user_id = int(get_jwt_identity())
    try:
        schema = WebsiteUpdateSchema()
        data = schema.load(request.json)

        website = WebsiteService.update_website(website_id, user_id, **data)

        response_schema = WebsiteSchema()
        return jsonify(response_schema.dump(website)), 200
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/<int:website_id>', methods=['DELETE'])
@jwt_required()
def delete_website(website_id):
    user_id = int(get_jwt_identity())
    try:
        WebsiteService.delete_website(website_id, user_id)
        return '', 204
    except ValueError as e:
        return jsonify({'error': str(e)}), 404


@bp.route('/seed', methods=['POST'])
@jwt_required()
def seed_websites():
    """Seed default websites for the current user"""
    user_id = int(get_jwt_identity())
    try:
        websites = WebsiteService.seed_default_websites(user_id)
        schema = WebsiteSchema(many=True)
        return jsonify({
            'message': f'Seeded {len(websites)} default websites',
            'websites': schema.dump(websites)
        }), 201
    except Exception as e:
        return jsonify({'error': str(e)}), 500

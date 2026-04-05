from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.extensions import db
from app.models.selector import Selector
from app.models.website import Website
from app.schemas.selector import SelectorSchema, SelectorCreateSchema

bp = Blueprint('selectors', __name__)


@bp.route('/websites/<int:website_id>/selectors', methods=['GET'])
@jwt_required()
def get_selectors(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    selectors = Selector.query.filter_by(website_id=website_id).all()

    schema = SelectorSchema(many=True)
    return jsonify(schema.dump(selectors)), 200


@bp.route('/websites/<int:website_id>/selectors', methods=['POST'])
@jwt_required()
def create_selector(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    try:
        schema = SelectorCreateSchema()
        data = schema.load(request.json)

        selector = Selector(website_id=website_id, **data)
        db.session.add(selector)
        db.session.commit()

        response_schema = SelectorSchema()
        return jsonify(response_schema.dump(selector)), 201

    except ValidationError as e:
        return jsonify({'error': e.messages}), 400


@bp.route('/selectors/<int:selector_id>', methods=['DELETE'])
@jwt_required()
def delete_selector(selector_id):
    user_id = int(get_jwt_identity())

    selector = Selector.query.join(Website).filter(
        Selector.id == selector_id,
        Website.user_id == user_id
    ).first()

    if not selector:
        return jsonify({'error': 'Selector not found'}), 404

    db.session.delete(selector)
    db.session.commit()

    return '', 204

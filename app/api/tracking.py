from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from marshmallow import ValidationError
from app.extensions import db
from app.models.tracking_rule import TrackingRule
from app.models.website import Website
from app.schemas.tracking_rule import TrackingRuleSchema, TrackingRuleCreateSchema

bp = Blueprint('tracking', __name__)


@bp.route('/websites/<int:website_id>/rules', methods=['GET'])
@jwt_required()
def get_tracking_rules(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    rules = TrackingRule.query.filter_by(website_id=website_id).all()

    schema = TrackingRuleSchema(many=True)
    return jsonify(schema.dump(rules)), 200


@bp.route('/websites/<int:website_id>/rules', methods=['POST'])
@jwt_required()
def create_tracking_rule(website_id):
    user_id = int(get_jwt_identity())

    website = Website.query.filter_by(id=website_id, user_id=user_id).first()
    if not website:
        return jsonify({'error': 'Website not found'}), 404

    try:
        schema = TrackingRuleCreateSchema()
        data = schema.load(request.json)

        rule = TrackingRule(website_id=website_id, **data)
        db.session.add(rule)
        db.session.commit()

        response_schema = TrackingRuleSchema()
        return jsonify(response_schema.dump(rule)), 201

    except ValidationError as e:
        return jsonify({'error': e.messages}), 400


@bp.route('/rules/<int:rule_id>', methods=['GET'])
@jwt_required()
def get_tracking_rule(rule_id):
    user_id = int(get_jwt_identity())

    rule = TrackingRule.query.join(Website).filter(
        TrackingRule.id == rule_id,
        Website.user_id == user_id
    ).first()

    if not rule:
        return jsonify({'error': 'Tracking rule not found'}), 404

    schema = TrackingRuleSchema()
    return jsonify(schema.dump(rule)), 200


@bp.route('/rules/<int:rule_id>', methods=['PUT'])
@jwt_required()
def update_tracking_rule(rule_id):
    user_id = int(get_jwt_identity())

    rule = TrackingRule.query.join(Website).filter(
        TrackingRule.id == rule_id,
        Website.user_id == user_id
    ).first()

    if not rule:
        return jsonify({'error': 'Tracking rule not found'}), 404

    try:
        schema = TrackingRuleCreateSchema()
        data = schema.load(request.json, partial=True)

        for key, value in data.items():
            setattr(rule, key, value)

        db.session.commit()

        response_schema = TrackingRuleSchema()
        return jsonify(response_schema.dump(rule)), 200

    except ValidationError as e:
        return jsonify({'error': e.messages}), 400


@bp.route('/rules/<int:rule_id>', methods=['DELETE'])
@jwt_required()
def delete_tracking_rule(rule_id):
    user_id = int(get_jwt_identity())

    rule = TrackingRule.query.join(Website).filter(
        TrackingRule.id == rule_id,
        Website.user_id == user_id
    ).first()

    if not rule:
        return jsonify({'error': 'Tracking rule not found'}), 404

    db.session.delete(rule)
    db.session.commit()

    return '', 204

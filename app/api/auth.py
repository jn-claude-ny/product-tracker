from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, create_access_token
from marshmallow import ValidationError
from app.services.auth_service import AuthService
from app.services.user_service import UserService
from app.schemas.user import UserSchema, UserCreateSchema, UserLoginSchema
from app.extensions import limiter

bp = Blueprint('auth', __name__)


@bp.route('/register', methods=['POST'])
@limiter.limit("5 per hour")
def register():
    try:
        schema = UserCreateSchema()
        data = schema.load(request.json)

        user = AuthService.register_user(data['email'], data['password'])
        tokens = AuthService.create_tokens(user)

        user_schema = UserSchema()
        return jsonify({
            'user': user_schema.dump(user),
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token']
        }), 201
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 400


@bp.route('/login', methods=['POST'])
@limiter.limit("5 per 5 minutes")
def login():
    try:
        schema = UserLoginSchema()
        data = schema.load(request.json)

        user = AuthService.authenticate_user(data['email'], data['password'])
        tokens = AuthService.create_tokens(user)

        user_schema = UserSchema()
        return jsonify({
            'user': user_schema.dump(user),
            'access_token': tokens['access_token'],
            'refresh_token': tokens['refresh_token']
        }), 200
    except ValidationError as e:
        return jsonify({'error': e.messages}), 400
    except ValueError as e:
        return jsonify({'error': str(e)}), 401


@bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    user_id = int(get_jwt_identity())
    user = UserService.get_user_by_id(user_id)
    
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    access_token = create_access_token(identity=str(user.id))
    refresh_token = create_refresh_token(identity=str(user.id))

    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token
    }), 200


@bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = int(get_jwt_identity())
    user = UserService.get_user_by_id(user_id)

    schema = UserSchema()
    return jsonify(schema.dump(user)), 200

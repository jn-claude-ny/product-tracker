from flask import Blueprint, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.services.user_service import UserService
from app.schemas.user import UserSchema

bp = Blueprint('users', __name__)


@bp.route('/me', methods=['GET'])
@jwt_required()
def get_current_user():
    user_id = int(get_jwt_identity())
    user = UserService.get_user_by_id(user_id)

    schema = UserSchema()
    return jsonify(schema.dump(user)), 200

import bcrypt
from flask_jwt_extended import create_access_token, create_refresh_token
from app.models.user import User
from app.extensions import db


class AuthService:
    @staticmethod
    def hash_password(password: str) -> str:
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    @staticmethod
    def verify_password(password: str, password_hash: str) -> bool:
        return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))

    @staticmethod
    def register_user(email: str, password: str) -> User:
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise ValueError('Email already registered')

        password_hash = AuthService.hash_password(password)
        user = User(email=email, password_hash=password_hash)
        db.session.add(user)
        db.session.commit()
        return user

    @staticmethod
    def authenticate_user(email: str, password: str) -> User:
        user = User.query.filter_by(email=email).first()
        if not user or not AuthService.verify_password(password, user.password_hash):
            raise ValueError('Invalid email or password')
        if not user.is_active:
            raise ValueError('Account is inactive')
        return user

    @staticmethod
    def create_tokens(user: User) -> dict:
        access_token = create_access_token(identity=str(user.id))
        refresh_token = create_refresh_token(identity=str(user.id))
        return {
            'access_token': access_token,
            'refresh_token': refresh_token
        }

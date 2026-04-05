from app.models.user import User
from app.extensions import db


class UserService:
    @staticmethod
    def get_user_by_id(user_id: int) -> User:
        user = User.query.get(user_id)
        if not user:
            raise ValueError('User not found')
        return user

    @staticmethod
    def get_user_by_email(email: str) -> User:
        return User.query.filter_by(email=email).first()

    @staticmethod
    def update_user(user_id: int, **kwargs) -> User:
        user = UserService.get_user_by_id(user_id)
        for key, value in kwargs.items():
            if hasattr(user, key):
                setattr(user, key, value)
        db.session.commit()
        return user

    @staticmethod
    def delete_user(user_id: int) -> None:
        user = UserService.get_user_by_id(user_id)
        db.session.delete(user)
        db.session.commit()

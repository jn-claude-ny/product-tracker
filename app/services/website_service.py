from app.models.website import Website
from app.extensions import db


class WebsiteService:
    @staticmethod
    def create_website(user_id: int, **kwargs) -> Website:
        website = Website(user_id=user_id, **kwargs)
        db.session.add(website)
        db.session.commit()
        return website

    @staticmethod
    def get_website_by_id(website_id: int, user_id: int) -> Website:
        website = Website.query.filter_by(id=website_id, user_id=user_id).first()
        if not website:
            raise ValueError('Website not found')
        return website

    @staticmethod
    def get_user_websites(user_id: int):
        return Website.query.filter_by(user_id=user_id).all()

    @staticmethod
    def update_website(website_id: int, user_id: int, **kwargs) -> Website:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        for key, value in kwargs.items():
            if hasattr(website, key) and key not in ['id', 'user_id', 'created_at']:
                setattr(website, key, value)
        db.session.commit()
        return website

    @staticmethod
    def delete_website(website_id: int, user_id: int) -> None:
        website = WebsiteService.get_website_by_id(website_id, user_id)
        db.session.delete(website)
        db.session.commit()

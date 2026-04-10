from app.models.website import Website
from app.extensions import db


class WebsiteService:
    @staticmethod
    def seed_default_websites(user_id: int):
        """Seed default websites for a new user"""
        default_websites = [
            {
                'name': 'ASOS',
                'base_url': 'https://www.asos.com/',
                'allowed_domains': ['asos.com'],
                'sitemap_url': 'https://www.asos.com/sitemap.xml',
                'use_playwright': False,
                'scrape_delay_seconds': 2.0,
                'randomize_delay': True,
                'alert_cooldown_minutes': 60,
                'cron_schedule': '0 */6 * * *'  # Every 6 hours
            },
            {
                'name': "Champs Sports",
                'base_url': 'https://www.champssports.com',
                'allowed_domains': ['champssports.com', 'footlocker.com'],
                'sitemap_url': 'https://www.champssports.com/sitemap.xml',
                'use_playwright': False,
                'scrape_delay_seconds': 3.0,
                'randomize_delay': True,
                'proxy_group': 'brightdata',
                'alert_cooldown_minutes': 60,
                'cron_schedule': '0 */6 * * *'  # Every 6 hours
            },
            {
                'name': 'ShopWSS',
                'base_url': 'https://www.shopwss.com',
                'allowed_domains': ['shopwss.com'],
                'sitemap_url': 'https://www.shopwss.com/sitemap.xml',
                'use_playwright': False,
                'scrape_delay_seconds': 2.5,
                'randomize_delay': True,
                'alert_cooldown_minutes': 60,
                'cron_schedule': '0 */6 * * *'  # Every 6 hours
            }
        ]
        
        created_websites = []
        for website_data in default_websites:
            website = WebsiteService.create_website(user_id, **website_data)
            created_websites.append(website)
        
        return created_websites
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

from datetime import datetime
from app.extensions import db


class Website(db.Model):
    __tablename__ = 'websites'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    base_url = db.Column(db.String(512), nullable=False)
    allowed_domains = db.Column(db.JSON, default=list)
    sitemap_url = db.Column(db.String(512), nullable=False)
    use_playwright = db.Column(db.Boolean, default=False, nullable=False)
    wait_selector = db.Column(db.String(255))
    scrape_delay_seconds = db.Column(db.Numeric(5, 2), default=3.0, nullable=False)
    randomize_delay = db.Column(db.Boolean, default=True, nullable=False)
    proxy_group = db.Column(db.String(100))
    alert_cooldown_minutes = db.Column(db.Integer, default=60, nullable=False)
    cron_schedule = db.Column(db.String(100))
    discord_webhook_url = db.Column(db.String(512))
    
    # Crawl state tracking
    crawl_state = db.Column(db.String(20), default='never_crawled', nullable=False)  # never_crawled, crawling, paused, completed, failed
    crawl_progress = db.Column(db.Integer, default=0)
    total_products_expected = db.Column(db.Integer, default=0)
    products_discovered = db.Column(db.Integer, default=0)
    products_processed = db.Column(db.Integer, default=0)
    last_crawl_completed_at = db.Column(db.DateTime)
    
    sitemap_etag = db.Column(db.String(255))
    sitemap_last_checked = db.Column(db.DateTime)
    is_crawling = db.Column(db.Boolean, default=False, nullable=False)
    current_task_id = db.Column(db.String(255))
    last_error = db.Column(db.Text)
    last_error_at = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    categories = db.relationship('Category', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    selectors = db.relationship('Selector', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    tracking_rules = db.relationship('TrackingRule', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    discord_webhooks = db.relationship('DiscordWebhook', backref='website', lazy='dynamic', cascade='all, delete-orphan')
    products = db.relationship('Product', backref='website', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Website {self.name}>'

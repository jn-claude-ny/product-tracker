from datetime import datetime
from app.extensions import db


class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = (
        db.Index('idx_product_website_url', 'website_id', 'url'),
    )

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    url = db.Column(db.String(1024), nullable=False)
    sku = db.Column(db.String(255))
    title = db.Column(db.Text)
    brand = db.Column(db.String(255))
    image = db.Column(db.String(1024))
    categories = db.Column(db.JSON, default=list)
    
    # V2 fields (from migration 002)
    gender = db.Column(db.String(50))
    category = db.Column(db.String(255))
    color = db.Column(db.String(100))
    price_current = db.Column(db.Numeric(10, 2))
    price_previous = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10), default='USD')
    is_new = db.Column(db.Boolean, default=False)
    is_on_sale = db.Column(db.Boolean, default=False)
    first_seen = db.Column(db.DateTime)
    last_seen = db.Column(db.DateTime)
    last_price_change = db.Column(db.DateTime)
    detail_last_fetched = db.Column(db.DateTime)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    snapshots = db.relationship('ProductSnapshot', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    alerts = db.relationship('Alert', backref='product', lazy='dynamic', cascade='all, delete-orphan')
    variants = db.relationship('ProductVariant', backref='product', lazy='dynamic', cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Product {self.title}>'

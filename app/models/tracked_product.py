from datetime import datetime
from app.extensions import db


class TrackedProduct(db.Model):
    __tablename__ = 'tracked_products'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)

    # Tracking settings
    priority = db.Column(db.Enum('now', 'urgent', 'high', 'moderate', 'normal', name='priority_enum'), default='normal', nullable=False)
    crawl_period_hours = db.Column(db.Integer, default=24, nullable=False)  # How often to check this product

    # Price change tracking (tracks relative to current/last price)
    price_direction = db.Column(db.Enum('above', 'below', name='price_direction_enum'), nullable=True)
    price_reference = db.Column(db.Numeric(10, 2), nullable=True)  # Price at time of setting up tracking

    # Legacy price tracking criteria (kept for backward compatibility)
    price_condition = db.Column(db.Enum('greater_than', 'less_than', 'equal_to', name='price_condition_enum'), nullable=True)
    price_threshold = db.Column(db.Numeric(10, 2), nullable=True)

    # Notification settings
    discord_webhook_url = db.Column(db.String(512), nullable=True)

    # Size filter (JSON array of sizes to track, null means all sizes)
    size_filter = db.Column(db.JSON, nullable=True)

    # Availability filter ('InStock', 'OutOfStock', 'LowStock', or null for any)
    availability_filter = db.Column(db.String(50), nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('tracked_products', lazy='dynamic', cascade='all, delete-orphan'))
    product = db.relationship('Product', backref=db.backref('tracked_products', lazy='dynamic', cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<TrackedProduct {self.product.title if self.product else "Unknown"}>'

    def to_dict(self):
        product_data = None
        if self.product:
            # Get latest price from snapshots
            latest_snapshot = self.product.snapshots.order_by(db.desc('created_at')).first() if hasattr(self.product, 'snapshots') else None
            latest_price = float(latest_snapshot.price) if latest_snapshot and latest_snapshot.price else None

            product_data = {
                'id': self.product.id,
                'title': self.product.title,
                'url': self.product.url,
                'image': self.product.image,
                'price': latest_price,
                'brand': self.product.brand,
                'sku': self.product.sku
            }

        return {
            'id': self.id,
            'product_id': self.product_id,
            'priority': self.priority,
            'crawl_period_hours': self.crawl_period_hours,
            'price_direction': self.price_direction,
            'price_reference': float(self.price_reference) if self.price_reference else None,
            'price_condition': self.price_condition,
            'price_threshold': float(self.price_threshold) if self.price_threshold else None,
            'size_filter': self.size_filter,
            'availability_filter': self.availability_filter,
            'discord_webhook_url': self.discord_webhook_url,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            'product': product_data
        }

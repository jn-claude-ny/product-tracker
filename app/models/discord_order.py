from datetime import datetime
from app.extensions import db


class DiscordOrder(db.Model):
    __tablename__ = 'discord_orders'

    id = db.Column(db.Integer, primary_key=True)
    discord_user_id = db.Column(db.String(64), nullable=False, index=True)
    discord_channel_id = db.Column(db.String(64), nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    alert_type = db.Column(
        db.Enum('restock', 'price_drop', name='discord_alert_type_enum'),
        nullable=False,
        default='restock',
    )
    size_filter = db.Column(db.String(100), nullable=True)
    status = db.Column(
        db.Enum('active', 'cancelled', name='discord_order_status_enum'),
        default='active',
        nullable=False,
        index=True,
    )
    last_alert_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('discord_orders', lazy='dynamic', cascade='all, delete-orphan'))
    product = db.relationship('Product', backref=db.backref('discord_orders', lazy='dynamic'))

    def __repr__(self):
        return f'<DiscordOrder #{self.id} discord_user={self.discord_user_id} status={self.status}>'

    def to_dict(self):
        return {
            'id': self.id,
            'discord_user_id': self.discord_user_id,
            'user_id': self.user_id,
            'product_id': self.product_id,
            'alert_type': self.alert_type,
            'size_filter': self.size_filter,
            'status': self.status,
            'last_alert_at': self.last_alert_at.isoformat() if self.last_alert_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
        }

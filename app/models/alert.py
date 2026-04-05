from datetime import datetime
from app.extensions import db


class Alert(db.Model):
    __tablename__ = 'alerts'
    __table_args__ = (
        db.Index('idx_alert_product_type_hash', 'product_id', 'alert_type', 'state_hash'),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    alert_type = db.Column(db.String(50), nullable=False)
    state_hash = db.Column(db.String(64), nullable=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Alert {self.alert_type} for product {self.product_id}>'

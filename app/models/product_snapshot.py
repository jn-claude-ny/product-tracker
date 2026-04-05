from datetime import datetime
from app.extensions import db


class ProductSnapshot(db.Model):
    __tablename__ = 'product_snapshots'
    __table_args__ = (
        db.Index('idx_snapshot_product_created', 'product_id', 'created_at'),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False, index=True)
    price = db.Column(db.Numeric(10, 2))
    currency = db.Column(db.String(10))
    availability = db.Column(db.String(50))
    hash = db.Column(db.String(64), index=True)
    extra_data = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self):
        return f'<ProductSnapshot {self.id} for product {self.product_id}>'

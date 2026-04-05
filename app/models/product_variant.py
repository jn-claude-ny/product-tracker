"""
Product Variant Model
Tracks size and color variants for products with individual availability and pricing.
"""
from datetime import datetime
from app.extensions import db


class ProductVariant(db.Model):
    """Individual product variant (size/color combination)"""
    __tablename__ = 'product_variants'
    __table_args__ = (
        db.Index('idx_variant_product', 'product_id'),
        db.Index('idx_variant_product_sku', 'product_id', 'variant_sku'),
    )

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id', ondelete='CASCADE'), nullable=False)
    variant_sku = db.Column(db.String(255), nullable=False)
    size = db.Column(db.String(50))
    color = db.Column(db.String(100))
    stock_state = db.Column(db.String(20))  # 'InStock', 'OutOfStock', 'LowStock'
    last_checked = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    first_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_in_stock = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<ProductVariant {self.variant_sku} - {self.size}/{self.color}>'

    def to_dict(self):
        """Convert variant to dictionary"""
        return {
            'id': self.id,
            'product_id': self.product_id,
            'variant_sku': self.variant_sku,
            'size': self.size,
            'color': self.color,
            'stock_state': self.stock_state,
            'last_checked': self.last_checked.isoformat() if self.last_checked else None,
            'first_seen': self.first_seen.isoformat() if self.first_seen else None,
            'last_in_stock': self.last_in_stock.isoformat() if self.last_in_stock else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

from app.extensions import db


class TrackingRule(db.Model):
    __tablename__ = 'tracking_rules'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    name = db.Column(db.String(255))
    rule_type = db.Column(db.String(50), nullable=False)
    rule_value = db.Column(db.String(512), nullable=False)
    alert_on_new = db.Column(db.Boolean, default=True, nullable=False)
    alert_on_price_drop = db.Column(db.Boolean, default=True, nullable=False)
    alert_on_back_in_stock = db.Column(db.Boolean, default=True, nullable=False)
    price_threshold_type = db.Column(db.String(20))
    price_threshold_value = db.Column(db.Numeric(10, 2))
    min_price = db.Column(db.Numeric(10, 2))
    max_price = db.Column(db.Numeric(10, 2))
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<TrackingRule {self.name}>'

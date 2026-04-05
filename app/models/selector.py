from datetime import datetime
from app.extensions import db


class Selector(db.Model):
    __tablename__ = 'selectors'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    field_name = db.Column(db.String(100), nullable=False)
    selector_type = db.Column(db.String(20), default='css', nullable=False)
    selector_value = db.Column(db.Text, nullable=False)
    post_process = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<Selector {self.field_name} for website {self.website_id}>'

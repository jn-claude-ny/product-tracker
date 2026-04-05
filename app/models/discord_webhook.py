from app.extensions import db


class DiscordWebhook(db.Model):
    __tablename__ = 'discord_webhooks'

    id = db.Column(db.Integer, primary_key=True)
    website_id = db.Column(db.Integer, db.ForeignKey('websites.id', ondelete='CASCADE'), nullable=False, index=True)
    webhook_url = db.Column(db.String(512), nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    def __repr__(self):
        return f'<DiscordWebhook for website {self.website_id}>'

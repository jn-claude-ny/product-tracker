from datetime import datetime
from app.extensions import db


class UserDiscordLink(db.Model):
    __tablename__ = 'user_discord_links'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, unique=True, index=True)
    discord_id = db.Column(db.String(64), nullable=False, unique=True, index=True)
    discord_name = db.Column(db.String(255), nullable=False)
    discord_avatar_url = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    user = db.relationship('User', backref=db.backref('discord_link', uselist=False, cascade='all, delete-orphan'))

    def __repr__(self):
        return f'<UserDiscordLink user_id={self.user_id} discord_id={self.discord_id}>'

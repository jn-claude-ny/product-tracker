from datetime import datetime
from app.extensions import db


class DiscordPendingUser(db.Model):
    __tablename__ = 'discord_pending_users'

    id = db.Column(db.Integer, primary_key=True)
    discord_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    discord_name = db.Column(db.String(255), nullable=False)
    discord_avatar_url = db.Column(db.String(512), nullable=True)
    reason = db.Column(db.Text, nullable=True)
    request_status = db.Column(
        db.Enum('pending', 'approved', 'rejected', name='discord_request_status_enum'),
        default='pending',
        nullable=False,
        index=True,
    )
    rejection_reason = db.Column(db.Text, nullable=True)
    admin_message_id = db.Column(db.String(64), nullable=True)
    admin_channel_id = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self):
        return f'<DiscordPendingUser {self.discord_name} ({self.request_status})>'

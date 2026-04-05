from app.api.auth import bp as auth_bp
from app.api.users import bp as users_bp
from app.api.websites import bp as websites_bp
from app.api.tracking import bp as tracking_bp
from app.api.alerts import bp as alerts_bp
from app.api.search import bp as search_bp
from app.api.health import bp as health_bp

__all__ = ['auth_bp', 'users_bp', 'websites_bp', 'tracking_bp', 'alerts_bp', 'search_bp', 'health_bp']

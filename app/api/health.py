from flask import Blueprint, jsonify
from app.extensions import db
import redis
from app.config import Config

bp = Blueprint('health', __name__)


@bp.route('/health', methods=['GET'])
def health_check():
    health_status = {
        'status': 'healthy',
        'database': 'unknown',
        'redis': 'unknown'
    }

    try:
        db.session.execute(db.text('SELECT 1'))
        health_status['database'] = 'healthy'
    except Exception:
        health_status['database'] = 'unhealthy'
        health_status['status'] = 'unhealthy'

    try:
        r = redis.from_url(Config.REDIS_URL)
        r.ping()
        health_status['redis'] = 'healthy'
    except Exception:
        health_status['redis'] = 'unhealthy'
        health_status['status'] = 'unhealthy'

    status_code = 200 if health_status['status'] == 'healthy' else 503
    return jsonify(health_status), status_code

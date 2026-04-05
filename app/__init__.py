from flask import Flask

from flask_cors import CORS

from prometheus_flask_exporter import PrometheusMetrics

import sentry_sdk

from sentry_sdk.integrations.flask import FlaskIntegration



from app.config import Config

from app.extensions import db, migrate, jwt, limiter, socketio





def create_app(config_class=Config):

    app = Flask(__name__)

    app.config.from_object(config_class)



    if app.config.get('SENTRY_DSN'):

        sentry_sdk.init(

            dsn=app.config['SENTRY_DSN'],

            integrations=[FlaskIntegration()],

            traces_sample_rate=0.1,

            environment=app.config.get('FLASK_ENV', 'production')

        )



    CORS(app, origins=app.config['CORS_ORIGINS'])



    db.init_app(app)

    migrate.init_app(app, db)

    jwt.init_app(app)

    limiter.init_app(app)

    socketio.init_app(app, cors_allowed_origins=app.config['CORS_ORIGINS'], message_queue=app.config['REDIS_URL'])



    PrometheusMetrics(app)



    from app.api import auth_bp, users_bp, websites_bp, tracking_bp, alerts_bp, search_bp, health_bp

    from app.api.crawl import bp as crawl_bp

    from app.api.selectors import bp as selectors_bp

    from app.api.webhooks import bp as webhooks_bp

    from app.api.views import bp as views_bp

    from app.api.tracked_products import bp as tracked_products_bp

    from app.api.products import bp as products_bp

    app.register_blueprint(views_bp)

    app.register_blueprint(auth_bp, url_prefix='/api/auth')

    app.register_blueprint(users_bp, url_prefix='/api/users')

    app.register_blueprint(websites_bp, url_prefix='/api/websites')

    app.register_blueprint(tracking_bp, url_prefix='/api/tracking')

    app.register_blueprint(alerts_bp, url_prefix='/api/alerts')

    app.register_blueprint(search_bp, url_prefix='/api/search')

    app.register_blueprint(selectors_bp, url_prefix='/api/selectors')

    app.register_blueprint(webhooks_bp, url_prefix='/api/webhooks')

    app.register_blueprint(tracked_products_bp, url_prefix='/api/tracked-products')

    app.register_blueprint(products_bp, url_prefix='/api/products')

    app.register_blueprint(crawl_bp, url_prefix='/api')

    app.register_blueprint(health_bp)



    from app.api import socketio_events  # noqa: F401 - imported for side effects



    return app


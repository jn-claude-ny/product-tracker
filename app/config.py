import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key-change-in-production')

    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'postgresql://postgres:postgres@localhost:5432/product_tracker')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_size': 2,  # Minimal pool to prevent connection exhaustion
        'max_overflow': 3,  # Very limited overflow
        'pool_recycle': 3600,  # Recycle connections after 1 hour
        'pool_pre_ping': True,  # Verify connections before use
        'pool_timeout': 30,  # Wait up to 30s for a connection
    }

    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    ELASTICSEARCH_URL = os.getenv('ELASTICSEARCH_URL', 'http://localhost:9200')

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'jwt-secret-key-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
    JWT_TOKEN_LOCATION = ['headers']
    JWT_HEADER_NAME = 'Authorization'
    JWT_HEADER_TYPE = 'Bearer'

    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

    BRIGHTDATA_PROXY_HOST = os.getenv('BRIGHTDATA_PROXY_HOST', '')
    BRIGHTDATA_PROXY_PORT = os.getenv('BRIGHTDATA_PROXY_PORT', '')
    BRIGHTDATA_PROXY_USERNAME = os.getenv('BRIGHTDATA_PROXY_USERNAME', '')
    BRIGHTDATA_PROXY_PASSWORD = os.getenv('BRIGHTDATA_PROXY_PASSWORD', '')

    SENTRY_DSN = os.getenv('SENTRY_DSN', '')

    CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:8081,http://localhost:5000,http://localhost:8080').split(',')

    RATELIMIT_STORAGE_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

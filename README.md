# Product Tracker Platform

Production-grade, multi-user e-commerce product tracking platform with automated scraping, real-time alerts, and intelligent scheduling.

## Architecture

- **Flask API** - REST + WebSocket for real-time updates
- **PostgreSQL** - Primary database with partitioned snapshots
- **Redis** - Caching, message broker, and pub/sub
- **Celery Workers** - Distributed task processing (crawl, scrape, alert, index queues)
- **Celery Beat** - Dynamic scheduler reading cron schedules from database
- **Playwright** - Browser automation with connection pooling
- **Elasticsearch** - Full-text product search with ILM policies
- **Nginx** - Reverse proxy and static file serving
- **Discord** - Rich embed alert notifications

## Quick Start

```bash
docker compose up --build
```

The application will be available at:
- **Web UI**: http://localhost:8080
- **API**: http://localhost:8080/api
- **Flower** (Celery monitoring): http://localhost:5555
- **Elasticsearch**: http://localhost:9200

## Initial Setup

1. Run database migrations:
```bash
docker compose exec flask alembic upgrade head
```

2. Access the web UI at http://localhost:8080 and register an account

3. Configure your first website:
   - Add website with sitemap URL
   - Configure CSS/XPath selectors for product fields
   - Create tracking rules (keyword, brand, category)
   - Add Discord webhook for alerts
   - Set cron schedule for automatic crawling

## API Endpoints

### Authentication
- `POST /auth/register` - Register new user
- `POST /auth/login` - Login (returns access + refresh tokens)
- `POST /auth/refresh` - Refresh access token
- `GET /auth/me` - Get current user info

### Websites
- `GET /websites` - List user's websites
- `POST /websites` - Create website
- `GET /websites/<id>` - Get website details
- `PUT /websites/<id>` - Update website
- `DELETE /websites/<id>` - Delete website
- `POST /websites/<id>/crawl` - Trigger manual crawl

### Selectors
- `GET /selectors/websites/<id>/selectors` - List selectors for website
- `POST /selectors/websites/<id>/selectors` - Create selector
- `DELETE /selectors/<id>` - Delete selector

### Tracking Rules
- `GET /tracking/websites/<id>/rules` - List tracking rules
- `POST /tracking/websites/<id>/rules` - Create tracking rule
- `GET /tracking/rules/<id>` - Get tracking rule
- `PUT /tracking/rules/<id>` - Update tracking rule
- `DELETE /tracking/rules/<id>` - Delete tracking rule

### Discord Webhooks
- `GET /webhooks/websites/<id>/webhooks` - List webhooks
- `POST /webhooks/websites/<id>/webhooks` - Create webhook
- `DELETE /webhooks/<id>` - Delete webhook

### Alerts
- `GET /alerts` - List user's alerts (paginated)
- Query params: `alert_type`, `product_id`, `page`, `page_size`

### Search
- `GET /search` - Search products (Elasticsearch)
- Query params: `q`, `website_id`, `brand`, `min_price`, `max_price`, `availability`, `categories`, `page`, `page_size`

### Health
- `GET /health` - Health check (database, Redis status)

## Features

### Sitemap Parsing
- Supports sitemap index and gzip compression
- ETag and Last-Modified caching
- URL normalization (removes tracking parameters)
- Proxy support via BrightData

### Scraping Engine
- **Fast mode**: HTTP requests with proxy rotation
- **Heavy mode**: Playwright browser pool with context reuse
- Configurable delays with randomization
- CSS and XPath selector support
- Post-processing: clean_price, extract_text, json_parse, etc.
- Hash-based change detection (skips unchanged products)

### Alert System
- **Alert types**: new_match, price_drop, back_in_stock
- **Matching rules**: keyword, brand, category
- **Price thresholds**: absolute or percentage
- **Cooldown**: prevents duplicate alerts
- **Discord embeds**: rich notifications with product details
- **Real-time**: WebSocket push to connected clients

### Dynamic Scheduler
- Reads cron schedules from database
- Reloads every minute (no restart required)
- Spreads load across workers
- Per-website scheduling

### Elasticsearch
- Full-text search on title, brand, SKU
- Filters: price range, availability, categories
- User isolation
- ILM policy: 30-day rollover, 90-day deletion

## Environment Variables

```env
FLASK_ENV=development
SECRET_KEY=<random-secret>
JWT_SECRET_KEY=<random-jwt-secret>

DATABASE_URL=postgresql://postgres:postgres@postgres:5432/product_tracker
REDIS_URL=redis://redis:6379/0
ELASTICSEARCH_URL=http://elasticsearch:9200

CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

BRIGHTDATA_PROXY_HOST=
BRIGHTDATA_PROXY_PORT=
BRIGHTDATA_PROXY_USERNAME=
BRIGHTDATA_PROXY_PASSWORD=

SENTRY_DSN=

CORS_ORIGINS=http://localhost:8080,http://localhost:5000
```

## Monitoring

- **Flower**: http://localhost:5555 - Monitor Celery tasks, workers, queues
- **Prometheus**: `/metrics` endpoint - Application metrics
- **Logs**: JSON structured logging to stdout
- **Sentry**: Error tracking (if DSN configured)

## Scaling

### Horizontal Scaling
- Add more workers for specific queues:
  ```bash
  docker compose up --scale celery_worker_scrape=4
  ```

### Queue Priorities
- `high_priority` - User-triggered crawls
- `crawl_queue` - Scheduled crawls
- `scrape_queue` - Product scraping
- `alert_queue` - Alert sending
- `index_queue` - Elasticsearch indexing

### Database Optimization
- Indexes on foreign keys, product URLs, timestamps
- Partitioning ready for `product_snapshots` table (monthly)
- Connection pooling configured

## Development

### Tech Stack
- **Backend**: Flask 3.0, SQLAlchemy 2.0, Celery 5.3
- **Frontend**: HTMX, Alpine.js, Tailwind CSS
- **Auth**: Flask-JWT-Extended with bcrypt
- **Validation**: Marshmallow schemas
- **Rate Limiting**: Flask-Limiter
- **WebSockets**: Flask-SocketIO with Redis pub/sub

### Project Structure
```
product-tracker/
├── app/                    # Flask application
│   ├── api/               # API blueprints
│   ├── models/            # SQLAlchemy models
│   ├── schemas/           # Marshmallow schemas
│   ├── services/          # Business logic
│   ├── scraping/          # Scraping engine
│   ├── search/            # Elasticsearch client
│   └── templates/         # Jinja2 templates
├── celery_app/            # Celery tasks
│   ├── tasks/             # Task modules
│   ├── celery.py          # Celery config
│   └── beat_scheduler.py  # Dynamic scheduler
├── docker/                # Dockerfiles
├── alembic/               # Database migrations
└── scrapy_project/        # (Reserved for future Scrapy integration)
```

## Production Deployment

1. Generate secure secrets:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

2. Configure environment variables in `.env`

3. Set up BrightData proxy (optional but recommended)

4. Deploy with Docker Compose or Kubernetes

5. Run migrations:
   ```bash
   alembic upgrade head
   ```

6. Configure Sentry DSN for error tracking

7. Set up SSL/TLS with Let's Encrypt (update nginx.conf)

## License

Proprietary

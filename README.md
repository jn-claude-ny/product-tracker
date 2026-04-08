# Product Tracker

Multi-site e-commerce product tracker with automated scraping, variant/size tracking, price alerts, and Discord notifications. Supports **ASOS**, **Shop WSS**, and **Champs Sports**.

![Dashboard](docs/screenshots/websites_info.png)

---

## Table of Contents

1. [Architecture](#architecture)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Configuration](#configuration)
5. [Running the App](#running-the-app)
6. [First-Time Setup](#first-time-setup)
7. [Usage](#usage)
8. [Tracked Products & Alerts](#tracked-products--alerts)
9. [API Reference](#api-reference)
10. [Project Structure](#project-structure)
11. [Celery Workers & Queues](#celery-workers--queues)
12. [Monitoring](#monitoring)

---

## Architecture

| Component | Purpose |
|---|---|
| **Flask** | REST API + Jinja2 UI + WebSocket (SocketIO) |
| **PostgreSQL** | Products, variants, snapshots, alerts, tracked products |
| **Redis** | Celery broker/backend + pub/sub for real-time alerts |
| **Celery Workers** | Distributed async task processing |
| **Celery Beat** | Periodic scheduled crawls |
| **Elasticsearch** | Full-text product search |
| **Nginx** | Reverse proxy + static assets |
| **BrightData** | Residential proxy for scraping |

---

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) + [Docker Compose](https://docs.docker.com/compose/) (v2)
- A **BrightData** account with a residential proxy zone (required for Champs Sports; optional for ASOS/WSS)
- A **Discord webhook URL** (one per site you want alerts for)

---

## Installation

```bash
git clone <repo-url>
cd product-tracker
cp .env.example .env
```

Edit `.env` with your secrets (see [Configuration](#configuration)), then:

```bash
docker compose up --build -d
```

---

## Configuration

All configuration is via `.env`. Copy `.env.example` as a starting point:

```env
# Flask
FLASK_ENV=production
SECRET_KEY=<generate with: python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<generate separately>

# Database
DATABASE_URL=postgresql://postgres:postgres@postgres:5432/product_tracker

# Redis
REDIS_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/1

# BrightData residential proxy (required for Champs Sports)
BRIGHTDATA_PROXY_HOST=brd.superproxy.io
BRIGHTDATA_PROXY_PORT=33335
BRIGHTDATA_PROXY_USERNAME=<your-brightdata-username>
BRIGHTDATA_PROXY_PASSWORD=<your-brightdata-password>

# Optional
SENTRY_DSN=
CORS_ORIGINS=http://localhost,http://localhost:5000,http://<YOUR_SERVER_IP>
```

> **Security**: never commit `.env`. It is in `.gitignore`.

---

## Running the App

### Start everything

```bash
docker compose up -d
```

### Stop

```bash
docker compose down
```

### Rebuild after code changes

```bash
docker compose up -d --build
```

> **Note**: `app/` and `celery_app/` are volume-mounted, so Python code changes in those directories take effect after restarting the relevant container — no rebuild required:
>
> ```bash
> docker compose restart celery_worker_scrape   # after scraper changes
> docker compose restart celery_worker_alert    # after alert task changes
> docker compose restart flask                  # after API/template changes
> ```

### Access

| URL | Service |
|---|---|
| http://localhost | Web UI (via Nginx, port 80) |
| http://localhost:5000 | Flask direct |
| http://localhost:5555 | Flower (Celery monitor) |
| http://localhost:9500 | Elasticsearch |

---

## First-Time Setup

### 1. Run database migrations

```bash
docker compose exec flask alembic upgrade head
```

### 2. Register an account

Open `http://localhost`, click **Register**, and create your account.

![Login](docs/screenshots/login.png)

### 3. Configure Discord webhooks

The three supported sites — **ASOS**, **Shop WSS**, and **Champs Sports** — are pre-configured in the app. You do not need to add them manually. On the Dashboard, click **Configure** on each site card to set a **Discord webhook URL** for site-level notifications.

### 4. Run your first crawl

On the Dashboard, click **Update** on a site card. This discovers products and populates the database. The crawl runs in the background — watch progress on the dashboard or via:

```bash
docker compose logs -f celery_worker_crawl
```

### 5. Browse products

Once the crawl completes the progress bar hits 100% and you can click through to **Products**.

![Dashboard with websites](docs/screenshots/websites_info.png)

---

## Usage

### Product Catalog

The Products page shows all discovered items across all crawled sites with real-time price, availability badge, and inventory count.

![Products](docs/screenshots/products.png)

### Search & Filters

Filter by keyword, website, gender, stock status, and price. Toggle **New Arrivals** or **On Sale** badges to quickly surface deals and restocks.

![Search and filters](docs/screenshots/Search_and_filters.png)

![Sale and new badges](docs/screenshots/sale_and_new_filters.png)

![All filters active](docs/screenshots/all_filters.png)

---

## Tracked Products & Alerts

### Your tracked products list

The dashboard shows all products you are currently tracking with their live size availability grid, schedule, and next check countdown. Click **Run Now** to trigger an immediate scrape without waiting for the schedule.

![Tracked products](docs/screenshots/tracked_products.png)

### Tracking a product

Click **Track** on any product card to open the tracking dialog.

![Track product dialog](docs/screenshots/Track_product.png)

Configure your alert rules:

**Price alert — alert when price decreases below current**

![Price decrease alert](docs/screenshots/Track_price_decrease.png)

**Price alert — alert when price increases above current**

![Price increase alert](docs/screenshots/Track_price_increase.png)

**Availability filter** — only alert for a specific stock state

![Availability filter](docs/screenshots/Track_availability.png)

**Priority** — controls how frequently the product is re-checked

| Priority | Re-check interval |
|---|---|
| ⚡ Instant (Now) | Immediately / on demand |
| 🔴 Urgent | ~5 min |
| 🟠 High | ~15 min |
| 🟡 Moderate | ~30 min |
| 🟢 Normal | ~1 hour |

![Priority selector](docs/screenshots/Track_priority.png)

**Check Schedule** — independent recurring schedule on top of priority

![Schedule selector](docs/screenshots/Track_schedule.png)

### Alert types

| Type | When fired |
|---|---|
| `price_drop` | Current price drops below your reference price |
| `price_increase` | Current price rises above your reference price |
| `availability_match` | A tracked size matches your availability filter |

### Discord notifications

Alerts are delivered as rich Discord embeds including product name (clickable link), brand, price, size, availability status, inventory count, and product image.

![Discord alerts](docs/screenshots/Discord_alerts.png)

### Cooldowns

Each website has a configurable `alert_cooldown_minutes` (default: 60 min). The same alert for the same product + state won't be re-sent within the cooldown window.

---

## API Reference

All endpoints are prefixed with `/api`. Authentication uses **JWT Bearer tokens**.

```bash
# Login
curl -X POST http://localhost:5000/api/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email": "user@example.com", "password": "yourpassword"}'
# Returns: { "access_token": "...", "refresh_token": "..." }
```

### Auth

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/register` | Register new account |
| POST | `/api/auth/login` | Login, get tokens |
| POST | `/api/auth/refresh` | Refresh access token |
| GET | `/api/auth/me` | Current user info |

### Websites

| Method | Path | Description |
|---|---|---|
| GET | `/api/websites` | List websites |
| PUT | `/api/websites/<id>` | Update website settings (webhook, schedule, etc.) |
| POST | `/api/websites/<id>/crawl` | Trigger crawl |

### Products

| Method | Path | Description |
|---|---|---|
| GET | `/api/products` | List products (paginated, filterable) |
| GET | `/api/products/<id>` | Get product + variants |

Query params: `website_id`, `gender`, `search`, `availability`, `is_new`, `is_on_sale`, `min_price`, `max_price`, `sort_by`, `sort_order`, `page`, `per_page`

### Tracked Products

| Method | Path | Description |
|---|---|---|
| GET | `/api/tracked-products` | List tracked products |
| POST | `/api/tracked-products` | Track a product |
| PUT | `/api/tracked-products/<id>` | Update tracking settings |
| DELETE | `/api/tracked-products/<id>` | Untrack |
| POST | `/api/tracked-products/<id>/run` | Trigger immediate check |

### Alerts

| Method | Path | Description |
|---|---|---|
| GET | `/api/alerts` | List alerts (paginated) |

### Search

| Method | Path | Description |
|---|---|---|
| GET | `/api/search` | Full-text search (Elasticsearch) |

Query params: `q`, `website_id`, `brand`, `min_price`, `max_price`, `availability`, `page`, `per_page`

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Service health check |

---

## Project Structure

```
product-tracker/
├── app/
│   ├── api/                  # Flask API blueprints
│   │   ├── auth.py
│   │   ├── products.py
│   │   ├── tracked_products.py
│   │   ├── alerts.py
│   │   ├── websites.py
│   │   ├── search.py
│   │   └── ...
│   ├── models/               # SQLAlchemy models
│   │   ├── product.py
│   │   ├── product_variant.py
│   │   ├── product_snapshot.py
│   │   ├── tracked_product.py
│   │   ├── alert.py
│   │   ├── website.py
│   │   └── user.py
│   ├── scraping/             # Site scrapers
│   │   ├── asos_scraper.py
│   │   ├── shopwss_scraper.py
│   │   ├── champssports_scraper.py
│   │   ├── scraper_factory.py
│   │   └── base_scraper.py
│   └── templates/            # Jinja2 + Alpine.js UI
│       ├── dashboard.html
│       ├── products.html
│       └── ...
├── celery_app/
│   ├── tasks/
│   │   ├── crawl_tasks.py            # Site discovery crawls
│   │   ├── scrape_tasks.py           # Per-product scraping + snapshots
│   │   ├── tracked_product_tasks.py  # Tracked product check chains
│   │   ├── alert_tasks.py            # Alert evaluation + Discord sending
│   │   ├── discovery_tasks.py        # Product upsert helpers
│   │   └── index_tasks.py            # Elasticsearch indexing
│   ├── celery.py              # Celery app + task routing
│   └── beat_scheduler.py      # Dynamic periodic scheduler
├── alembic/                   # DB migration scripts
├── docs/
│   └── screenshots/           # UI screenshots used in this README
├── docker/
│   ├── flask.Dockerfile
│   └── worker.Dockerfile
├── nginx/
│   └── nginx.conf
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## Celery Workers & Queues

| Worker | Queue | Purpose |
|---|---|---|
| `celery_worker_crawl` | `crawl_queue` | Crawl websites, discover products |
| `celery_worker_scrape` | `scrape_queue` | Scrape individual product details/variants |
| `celery_worker_alert` | `alert_queue` | Evaluate alert rules, send Discord notifications |
| `celery_worker_index` | `index_queue` | Index products to Elasticsearch |
| `celery_worker_urgent_now` | `urgent_now` | Immediate/manual tracked product checks |
| `celery_worker_high_priority` | `high_priority` | High-priority scheduled checks |
| `celery_worker_moderate_priority` | `moderate_priority` | Moderate-priority checks |
| `celery_worker_normal_priority` | `normal_priority` | Normal-priority checks |
| `celery_beat` | — | Periodic task scheduler |

### Task chain for tracked product checks

```
trigger_tracked_product_now
  └─► scrape_product          (scrape_queue)
        └─► on_scrape_complete (alert_queue)
              └─► evaluate_tracked_product_alerts (alert_queue)
                    └─► send_discord_alert (alert_queue)
```

---

## Monitoring

- **Flower** at http://localhost:5555 — real-time Celery task/worker/queue dashboard
- **Worker logs**:
  ```bash
  docker compose logs -f celery_worker_scrape celery_worker_alert
  ```
- **Flask logs**:
  ```bash
  docker compose logs -f flask
  ```
- **All services**:
  ```bash
  docker compose logs -f
  ```

---

## License

Proprietary

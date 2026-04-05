# Celery Queue System - How It Works

## Why Crawls Don't Start Immediately

When you click "Start" on a website crawl, the task is **queued** but may not execute immediately. Here's why:

### Queue Architecture

```
┌─────────────────┐
│  Click "Start"  │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Task sent to Redis (broker)    │
│  Queue: crawl_queue              │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Celery Worker picks up task    │
│  Worker: celery_worker_crawl    │
│  Concurrency: 2 workers          │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Task executes (crawl_website)  │
│  Creates discovery_tasks         │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Discovery tasks queued          │
│  Queue: scrape_queue             │
└────────┬────────────────────────┘
         │
         ▼
┌─────────────────────────────────┐
│  Celery Worker picks up tasks   │
│  Worker: celery_worker_scrape   │
│  Concurrency: 4 workers          │
└─────────────────────────────────┘
```

## Current Queue Configuration

### Queues
1. **crawl_queue** - Handles website crawl initiation
2. **scrape_queue** - Handles product discovery and detail extraction
3. **alert_queue** - Handles price alerts and notifications
4. **index_queue** - Handles search indexing

### Workers

**celery_worker_crawl:**
- Listens to: `crawl_queue`
- Concurrency: 2 workers
- Purpose: Start crawls, analyze sitemaps, queue discovery tasks

**celery_worker_scrape:**
- Listens to: `scrape_queue`
- Concurrency: 4 workers
- Purpose: Discover products, extract details, save to database

### Why Delays Happen

1. **Worker Busy**: If both crawl workers are busy, new tasks wait in queue
2. **Sequential Processing**: With `worker_prefetch_multiplier=1`, workers only take 1 task at a time
3. **Long-Running Tasks**: Discovery tasks can take 40-80 seconds per gender
4. **Database Connections**: Connection pool limits can slow down processing

## Current Settings (celery.py)

```python
worker_prefetch_multiplier=1  # Workers take 1 task at a time
worker_max_tasks_per_child=1000  # Restart worker after 1000 tasks
task_acks_late=True  # Acknowledge task after completion
task_time_limit=3600  # Max 1 hour per task
task_soft_time_limit=3000  # Soft limit 50 minutes
```

## How to Speed Up Crawls

### Option 1: Increase Worker Concurrency
```yaml
# docker-compose.yml
celery_worker_crawl:
  command: celery -A celery_app.celery worker -Q crawl_queue -c 4  # Was 2
```

### Option 2: Increase Prefetch
```python
# celery.py
worker_prefetch_multiplier=2  # Workers can prefetch 2 tasks
```

### Option 3: Add More Workers
```yaml
# docker-compose.yml
celery_worker_crawl_2:
  command: celery -A celery_app.celery worker -Q crawl_queue -c 2
```

## Monitoring Queue Status

### Check Queue Length
```bash
docker compose exec flask python -c "
from celery_app.celery import celery
from celery.task.control import inspect
i = inspect()
print('Active:', i.active())
print('Reserved:', i.reserved())
print('Scheduled:', i.scheduled())
"
```

### Check Redis Queue
```bash
docker compose exec redis redis-cli LLEN crawl_queue
docker compose exec redis redis-cli LLEN scrape_queue
```

## Task Flow Example

**User clicks "Start" on WSS:**

1. `00:00` - Task queued to `crawl_queue`
2. `00:01` - Worker picks up task (if available)
3. `00:02` - `crawl_website` executes
4. `00:03` - Creates 2 discovery tasks (men, women)
5. `00:03` - Discovery tasks queued to `scrape_queue`
6. `00:04` - Scrape workers pick up discovery tasks
7. `00:05-01:25` - Discovery tasks fetch products (80s each)
8. `01:25` - Products saved to database
9. `01:26` - Detail extraction tasks queued (50 products per batch)
10. `01:27-02:30` - Detail extraction completes

**Total Time: ~2.5 minutes for WSS (1,676 products)**

## Why You See Delays

If you click "Start" and nothing happens for 10-30 seconds:

1. **Check if workers are busy**: Other crawls may be running
2. **Check database connections**: Pool may be exhausted (fixed now)
3. **Check Redis**: Broker may be slow
4. **Check logs**: `docker compose logs celery_worker_crawl -f`

## Recommended Configuration for Faster Crawls

```yaml
# docker-compose.yml
celery_worker_crawl:
  command: celery -A celery_app.celery worker -Q crawl_queue -c 4  # Increase to 4

celery_worker_scrape:
  command: celery -A celery_app.celery worker -Q scrape_queue -c 6  # Increase to 6
```

```python
# celery.py
worker_prefetch_multiplier=2  # Allow prefetching
```

This will allow:
- 4 simultaneous crawl initiations
- 6 simultaneous product discovery/extraction tasks
- Faster overall throughput

**Trade-off**: More memory and database connections needed

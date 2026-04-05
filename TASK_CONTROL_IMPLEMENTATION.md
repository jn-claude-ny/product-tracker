# Task Control Implementation - Pause/Resume Actually Controls Celery Workers

## Problem Identified

**Issue:** UI showed progress and buttons, but Celery tasks kept running regardless of button clicks.

**Example:**
- Database: `crawl_state = 'paused'`, `is_crawling = False`
- Celery Reality: 4 active tasks running, 44 tasks queued
- UI showed "paused" but tasks were still processing products

## Root Cause

The original pause/resume endpoints only updated database state - they didn't actually control the Celery workers or task queues.

## Solution Implemented

### 1. Task-Level Pause Check

**File:** `celery_app/tasks/discovery_tasks.py`

Added check at the start of `extract_product_details_batch`:

```python
# Check if crawl is paused - abort task if so
if website.crawl_state == 'paused':
    logger.info(f'Crawl is paused for website {website_id}, aborting task')
    return {'status': 'aborted', 'message': 'Crawl is paused'}
```

**What this does:**
- Every task checks database state before processing
- If `crawl_state = 'paused'`, task exits immediately
- Prevents tasks from running when crawl is paused

### 2. Pause Endpoint - Actually Stops Tasks

**File:** `app/api/crawl.py`

Updated `pause_crawl()` to:

```python
# Stop all active and queued tasks for this website
stop_result = CrawlStateService.stop_website_crawl(website_id)

# Revoke current task if exists
if website.current_task_id:
    celery.control.revoke(website.current_task_id, terminate=True, signal='SIGKILL')

# Update database state
website.crawl_state = 'paused'
website.is_crawling = False
website.current_task_id = None
```

**What this does:**
1. Calls `CrawlStateService.stop_website_crawl()` to revoke active tasks
2. Purges queued tasks from the queue
3. Revokes the current task ID with SIGKILL
4. Updates database state to 'paused'

**Response includes:**
```json
{
  "status": "success",
  "message": "Crawl paused - stopped 4 tasks, removed 44 queued",
  "tasks_stopped": 4,
  "tasks_removed": 44
}
```

### 3. Resume Endpoint - Re-queues Remaining Work

**File:** `app/api/crawl.py`

Updated `resume_crawl()` to:

```python
# Find products that haven't been processed yet
unprocessed_products = Product.query.filter_by(
    website_id=website_id
).filter(
    Product.last_checked == None  # Products without details
).all()

if unprocessed_products:
    # Re-queue detail extraction tasks
    product_ids = [p.sku for p in unprocessed_products]
    batch_size = 50
    batches = [product_ids[i:i + batch_size] for i in range(0, len(product_ids), batch_size)]
    
    tasks = [extract_product_details_batch.s(website_id, batch) for batch in batches]
    job = group(tasks)
    job.apply_async(queue='scrape_queue')
    
    # Update state to crawling
    website.crawl_state = 'crawling'
    website.is_crawling = True
```

**What this does:**
1. Queries database for products without `last_checked` (not yet processed)
2. Creates batches of 50 products each
3. Queues new `extract_product_details_batch` tasks
4. Updates database state to 'crawling'

**Response includes:**
```json
{
  "status": "success",
  "message": "Crawl resumed - queued 14 batches (672 products)",
  "batches_queued": 14,
  "products_remaining": 672
}
```

## How It Works Now

### Pause Flow

1. **User clicks "Pause"** → Frontend calls `POST /api/websites/{id}/crawl/pause`
2. **Backend:**
   - Revokes all active tasks for this website
   - Purges all queued tasks from scrape_queue
   - Sets `crawl_state = 'paused'`
3. **Celery:**
   - Active tasks are terminated (SIGKILL)
   - Queued tasks are removed from queue
   - New tasks check state and abort if paused
4. **UI:**
   - Button changes from "Pause" to "Resume"
   - Progress bar shows orange (paused state)
   - No more progress updates

### Resume Flow

1. **User clicks "Resume"** → Frontend calls `POST /api/websites/{id}/crawl/resume`
2. **Backend:**
   - Queries for unprocessed products
   - Creates new task batches
   - Queues tasks to scrape_queue
   - Sets `crawl_state = 'crawling'`
3. **Celery:**
   - Workers pick up new tasks
   - Tasks process remaining products
   - Progress updates resume
4. **UI:**
   - Button changes from "Resume" to "Pause"
   - Progress bar shows purple gradient (crawling)
   - Progress percentage increases

## Testing Instructions

### Before Testing - Check Current State

**Check Celery activity:**
```bash
docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active
```

**Check queue length:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
```

**Check database state:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, name, crawl_state, is_crawling, products_processed, total_products_expected FROM websites WHERE id = 4;"
```

### Test 1: Pause Active Crawl

**Setup:** Start a crawl on ASOS (or any website)

1. **Before pause:**
   - Check active tasks: `celery inspect active` → Should show tasks
   - Check queue: `redis-cli LLEN scrape_queue` → Should have queued tasks
   - UI shows "Pause" button

2. **Click "Pause":**
   - Watch Flask logs for: `Stopped X active tasks and Y queued tasks`
   - Check active tasks again → Should be empty
   - Check queue again → Should be 0 or much smaller
   - UI button changes to "Resume"

3. **Verify tasks stopped:**
   - Database progress should stop increasing
   - No new products being processed
   - `crawl_state = 'paused'`

### Test 2: Resume Paused Crawl

**Setup:** Have a paused crawl with unprocessed products

1. **Before resume:**
   - Check unprocessed products count
   - Queue should be empty
   - UI shows "Resume" button

2. **Click "Resume":**
   - Watch Flask logs for: `Re-queued X batches for detail extraction`
   - Check queue: Should have new tasks
   - UI button changes to "Pause"

3. **Verify tasks resumed:**
   - Active tasks should appear
   - Progress should start increasing again
   - Products being processed
   - `crawl_state = 'crawling'`

### Test 3: Pause Check in Tasks

**Setup:** Manually set `crawl_state = 'paused'` while tasks are queued

```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "UPDATE websites SET crawl_state = 'paused' WHERE id = 4;"
```

**Expected:**
- Tasks that start after this will check state
- They will abort with message: `Crawl is paused for website X, aborting task`
- No products will be processed
- Tasks exit cleanly

## Monitoring Commands

**Watch Flask logs:**
```bash
docker compose logs flask -f --tail 50
```

**Watch Celery worker logs:**
```bash
docker compose logs celery_worker_scrape -f --tail 50
```

**Check active tasks:**
```bash
docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active
```

**Check queue length:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
```

**Check database state:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, name, crawl_state, is_crawling, crawl_progress, products_processed, total_products_expected FROM websites;"
```

## What to Look For

### Successful Pause

- ✅ Active tasks count drops to 0
- ✅ Queue length drops significantly (or to 0)
- ✅ Flask logs show: `Stopped X active tasks and Y queued tasks`
- ✅ Database: `crawl_state = 'paused'`, `is_crawling = False`
- ✅ UI button changes to "Resume"
- ✅ Progress stops increasing

### Successful Resume

- ✅ New tasks appear in active list
- ✅ Queue length increases
- ✅ Flask logs show: `Re-queued X batches`
- ✅ Database: `crawl_state = 'crawling'`, `is_crawling = True`
- ✅ UI button changes to "Pause"
- ✅ Progress starts increasing again

### Task Pause Check Working

- ✅ Celery logs show: `Crawl is paused for website X, aborting task`
- ✅ Task exits without processing products
- ✅ No errors or crashes
- ✅ Progress doesn't increase

## Summary

The pause/resume functionality now **actually controls Celery workers and tasks**, not just database state:

1. **Pause** → Revokes active tasks + purges queue + sets state
2. **Resume** → Re-queues remaining work + sets state
3. **Tasks** → Check state before processing, abort if paused

This ensures the UI state matches the actual worker activity.

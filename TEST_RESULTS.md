# Crawl State Test Results

## Current State Analysis

### Database State
```
ID | Name          | State     | Crawling | Total Products | Unprocessed
---|---------------|-----------|----------|----------------|------------
1  | champssports  | completed | false    | 2,950          | 2,950
2  | Champs Sports | paused    | false    | 71             | 71
3  | WSS           | paused    | false    | 2,509          | 2,509
4  | ASOS          | crawling  | true     | 6,287          | 6,287
```

### Celery State
- **Active Tasks**: 4 (all for ASOS ID 4)
- **Queue Length**: 88 tasks (all for ASOS)
- **Workers Online**: 2 nodes

## Why Only ASOS is Running

**Root Cause**: Only ASOS has `crawl_state = 'crawling'` and `is_crawling = true`

The other websites are:
- **champssports (ID 1)**: Marked as `completed` but has 2,950 unprocessed products → **State is incorrect**
- **Champs Sports (ID 2)**: Marked as `paused` → Needs resume
- **WSS (ID 3)**: Marked as `paused` → Needs resume

## Issues Found

### Issue 1: champssports Shows "Completed" But Has Unprocessed Products

**Problem**: Website ID 1 shows `crawl_state = 'completed'` but has 2,950 products with `detail_last_fetched IS NULL`

**Why**: The crawl likely failed or was interrupted before all products were processed, but the state wasn't updated correctly.

**Fix**: Either:
1. Click "Update" to start a new crawl
2. Manually set state to `paused` and click "Resume"

### Issue 2: Paused Websites Don't Auto-Resume

**Problem**: Websites 2 and 3 are paused and won't start processing until user clicks "Resume"

**Why**: This is by design - paused state requires manual intervention

**Fix**: Click "Resume" button on each website

## Test Cases to Execute

### Test 1: Pause ASOS (Currently Running)
**Expected**:
- Active tasks drop from 4 to 0
- Queue drops from 88 to 0 or very low
- State changes to `paused`
- UI button changes to "Resume"

### Test 2: Resume Champs Sports (ID 2)
**Expected**:
- 2 batches queued (71 products / 50 per batch = 2 batches)
- State changes to `crawling`
- UI button changes to "Pause"
- Tasks start processing

### Test 3: Resume WSS (ID 3)
**Expected**:
- 51 batches queued (2,509 products / 50 per batch = 51 batches)
- State changes to `crawling`
- UI button changes to "Pause"
- Tasks start processing

### Test 4: Update champssports (ID 1)
**Expected**:
- New crawl starts (discovery + detail extraction)
- State changes to `crawling`
- UI button changes to "Pause"
- Progress resets to 0%

## Manual Testing Steps

### Step 1: Test Pause on ASOS

**Before:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
# Expected: 88

docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active | grep -c "website_id.*4"
# Expected: 4 active tasks
```

**Action**: Click "Pause" on ASOS in dashboard

**After:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
# Expected: 0 or very low

docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active
# Expected: empty or no tasks for website 4
```

**Verify in UI**:
- Button changes from "Pause" to "Resume"
- Progress bar turns orange (paused state)

---

### Step 2: Test Resume on Champs Sports (ID 2)

**Before:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 2;"
# Expected: paused | f
```

**Action**: Click "Resume" on Champs Sports in dashboard

**After:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
# Expected: +2 tasks (or more if other websites also queued)

docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 2;"
# Expected: crawling | t
```

**Verify in UI**:
- Button changes from "Resume" to "Pause"
- Progress bar turns purple (crawling state)

---

### Step 3: Test Resume on WSS (ID 3)

**Before:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 3;"
# Expected: paused | f
```

**Action**: Click "Resume" on WSS in dashboard

**After:**
```bash
docker compose exec redis redis-cli LLEN scrape_queue
# Expected: +51 tasks

docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 3;"
# Expected: crawling | t
```

**Verify in UI**:
- Button changes from "Resume" to "Pause"
- Progress bar turns purple (crawling state)

---

### Step 4: Test Update on champssports (ID 1)

**Before:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 1;"
# Expected: completed | f
```

**Action**: Click "Update" on champssports in dashboard

**After:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT crawl_state, is_crawling FROM websites WHERE id = 1;"
# Expected: crawling | t

docker compose exec redis redis-cli LLEN crawl_queue
# Expected: 1 (new crawl task)
```

**Verify in UI**:
- Button changes from "Update" to "Pause"
- Progress bar resets and turns purple (crawling state)

---

## Expected Final State (After All Tests)

If all tests pass, all 4 websites should be crawling:

```
ID | Name          | State     | Crawling | Queue Tasks
---|---------------|-----------|----------|------------
1  | champssports  | crawling  | true     | Discovery + batches
2  | Champs Sports | crawling  | true     | 2 batches
3  | WSS           | crawling  | true     | 51 batches
4  | ASOS          | crawling  | true     | Re-queued batches
```

**Total Queue**: Should have 100+ tasks across all websites

**Active Tasks**: Should see tasks for multiple websites (not just ASOS)

## Monitoring Commands

**Watch all activity:**
```bash
# Terminal 1: Flask logs
docker compose logs flask -f --tail 50

# Terminal 2: Celery logs
docker compose logs celery_worker_scrape -f --tail 50

# Terminal 3: Queue monitoring
watch -n 2 'docker compose exec redis redis-cli LLEN scrape_queue'

# Terminal 4: Active tasks
watch -n 5 'docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active | grep -c "extract_product_details_batch"'
```

**Quick status check:**
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, name, crawl_state, is_crawling FROM websites ORDER BY id;"
```

## Summary

**Why only ASOS is running**: It's the only website with `crawl_state = 'crawling'`. The others are paused or incorrectly marked as completed.

**To fix**: Manually test each button (Pause, Resume, Update) to verify they properly control the Celery workers and update the database state.

**Next steps**: Execute the manual testing steps above and verify each case works correctly.

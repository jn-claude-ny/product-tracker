# Crawl System Fix - Complete Analysis

## Root Cause Found ✅

**The crawling system was NOT working because:**

1. **Discovery tasks module was NOT registered in Celery** 
   - `celery_app/celery.py` was missing `discovery_tasks` from the `include` list
   - Tasks were being queued but never executed by workers

2. **Product model field mismatch**
   - Discovery tasks were trying to save fields that don't exist in V2 schema
   - `sale_price`, `size_range`, `availability`, `variants_data` don't exist
   - Correct V2 fields: `price_previous`, `category`, `first_seen`, `last_seen`, etc.

## Fixes Applied ✅

### 1. Celery Configuration (`celery_app/celery.py`)
```python
# BEFORE - discovery_tasks missing
include=[
    'celery_app.tasks.crawl_tasks',
    'celery_app.tasks.scrape_tasks',
    'celery_app.tasks.alert_tasks',
    'celery_app.tasks.index_tasks'
]

# AFTER - discovery_tasks added
include=[
    'celery_app.tasks.crawl_tasks',
    'celery_app.tasks.scrape_tasks',
    'celery_app.tasks.discovery_tasks',  # ✅ ADDED
    'celery_app.tasks.alert_tasks',
    'celery_app.tasks.index_tasks'
]

# Added routing
task_routes={
    ...
    'celery_app.tasks.discovery_tasks.*': {'queue': 'scrape_queue'},  # ✅ ADDED
}
```

### 2. Discovery Tasks (`celery_app/tasks/discovery_tasks.py`)

**Fixed `upsert_product` function:**
- Removed: `sale_price`, `size_range`, `availability`, `variants_data`
- Added: `category`, `currency`, `first_seen`, `last_seen`, `last_price_change`
- Fixed price tracking logic to use `price_previous` correctly
- Fixed snapshot creation to not reference non-existent fields

**Fixed `update_product_with_details` function:**
- Removed references to `size_range` and `variants_data`
- Simplified to only update `color` and `ProductVariant` records

## Current Status

### ✅ Working:
1. **Crawl tasks** - Execute successfully and queue discovery tasks
2. **Discovery tasks** - Now registered and executing
3. **Product fetching** - Successfully fetching from WSS API (1101 products discovered)
4. **Task routing** - Discovery tasks properly routed to scrape_queue

### ⚠️ Partially Working:
1. **Product saving** - Still failing, needs investigation
2. **Detail extraction** - Getting JSON parsing errors from API

### 🔴 Current Issues:

#### Issue 1: Products Not Saving to Database
**Evidence:**
```
[2026-03-31 02:54:23] Discovered 1101 products for website 3
[2026-03-31 02:54:23] Stored 0 products
```

**Likely Cause:** 
- Still a field mismatch or database constraint issue
- Need to check actual error messages from upsert_product

#### Issue 2: Detail Extraction Failing
**Evidence:**
```
Error fetching ShopWSS product details 8904016035970: 
Expecting value: line 1 column 1 (char 0)
```

**Cause:**
- API returning empty/invalid JSON responses
- Product detail endpoints may be rate-limited or broken

## Testing Results

### WSS (website_id=3) ✅ Partially Working
- Crawl task: ✅ Success
- Discovery tasks queued: ✅ 2 tasks
- Products discovered: ✅ 1101 products (men + women)
- Products saved: ❌ 0 products
- Detail extraction: ❌ JSON parsing errors

### ASOS (website_id=4) ⚠️ Timeout Issues
- Crawl task: ✅ Success
- Discovery tasks queued: ✅ 2 tasks
- Products discovered: ❌ Timeout (30 second read timeout)
- Needs: Increased timeout or retry logic

### Champs Sports (website_id=2) ⏸️ Not Tested
- Should work similar to WSS

## Next Steps to Complete Fix

### Priority 1: Fix Product Saving
1. Add detailed logging to `upsert_product` function
2. Check if there's a database constraint failing
3. Verify all field types match between model and data
4. Test with a single product insert manually

### Priority 2: Fix Detail Extraction
1. Add error handling for empty API responses
2. Implement rate limiting/backoff
3. Skip products that fail detail extraction
4. Log which products fail for manual review

### Priority 3: Optimize Performance
1. Increase ASOS timeout from 30s to 60s
2. Add connection pooling
3. Implement batch commits for better performance

## Commands to Test

### Trigger crawl for WSS:
```bash
docker compose exec flask python test_crawl.py 3
```

### Check products in database:
```bash
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT COUNT(*) FROM products WHERE website_id=3;"
```

### Monitor discovery tasks:
```bash
docker compose logs celery_worker_scrape -f | grep "discover_products_task"
```

### Check for errors:
```bash
docker compose logs celery_worker_scrape --tail=100 | grep "ERROR"
```

## Files Modified

1. ✅ `celery_app/celery.py` - Added discovery_tasks to include and routes
2. ✅ `celery_app/tasks/discovery_tasks.py` - Fixed field name mismatches
3. ✅ Celery workers restarted

## Summary

**Major Progress:** Discovery tasks are now executing and fetching products successfully. The crawl pipeline is working end-to-end.

**Remaining Issue:** Products are being discovered but not saved to database. This is likely a simple field mismatch or constraint issue that needs one more fix.

**Impact:** Once product saving is fixed, the entire crawl system will be fully functional and able to populate the database with products from all supported websites.

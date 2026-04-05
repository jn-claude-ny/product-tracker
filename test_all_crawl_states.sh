#!/bin/bash
# Test script to verify all crawl states and controls

echo "=== CRAWL STATE TEST SUITE ==="
echo ""

# Get auth token
echo "1. Getting auth token..."
TOKEN=$(curl -s -X POST http://localhost:8081/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')

if [ "$TOKEN" = "null" ] || [ -z "$TOKEN" ]; then
    echo "❌ Failed to get auth token"
    exit 1
fi
echo "✅ Got auth token"
echo ""

# Test Case 1: Resume Champs Sports (ID 2) - paused with 71 unprocessed
echo "=== TEST 1: Resume Champs Sports (ID 2) ==="
echo "State: paused, Unprocessed: 71"
echo "Action: Resume"
curl -s -X POST http://localhost:8081/api/websites/2/crawl/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""
sleep 2

# Check queue
echo "Checking scrape_queue..."
docker compose exec redis redis-cli LLEN scrape_queue
echo ""

# Check active tasks
echo "Checking active tasks for website 2..."
docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active | grep -A 5 "website_id.*2" || echo "No active tasks for website 2"
echo ""

# Test Case 2: Resume WSS (ID 3) - paused with 2,509 unprocessed
echo "=== TEST 2: Resume WSS (ID 3) ==="
echo "State: paused, Unprocessed: 2,509"
echo "Action: Resume"
curl -s -X POST http://localhost:8081/api/websites/3/crawl/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""
sleep 2

# Check queue
echo "Checking scrape_queue..."
docker compose exec redis redis-cli LLEN scrape_queue
echo ""

# Test Case 3: Pause ASOS (ID 4) - currently crawling
echo "=== TEST 3: Pause ASOS (ID 4) ==="
echo "State: crawling, Active tasks: 4, Queue: ~88"
echo "Action: Pause"
curl -s -X POST http://localhost:8081/api/websites/4/crawl/pause \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""
sleep 2

# Check queue after pause
echo "Checking scrape_queue after pause..."
docker compose exec redis redis-cli LLEN scrape_queue
echo ""

# Check active tasks after pause
echo "Checking active tasks after pause..."
docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active | grep -c "extract_product_details_batch" || echo "0 active tasks"
echo ""

# Test Case 4: Resume ASOS (ID 4) - now paused
echo "=== TEST 4: Resume ASOS (ID 4) ==="
echo "State: paused (just paused), Unprocessed: ~6,287"
echo "Action: Resume"
curl -s -X POST http://localhost:8081/api/websites/4/crawl/resume \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""
sleep 2

# Check queue
echo "Checking scrape_queue..."
docker compose exec redis redis-cli LLEN scrape_queue
echo ""

# Test Case 5: Update champssports (ID 1) - completed but has unprocessed
echo "=== TEST 5: Update champssports (ID 1) ==="
echo "State: completed, Unprocessed: 2,950 (should be crawling!)"
echo "Action: Update (start new crawl)"
curl -s -X POST http://localhost:8081/api/websites/1/crawl \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" | jq '.'
echo ""
sleep 2

# Final state check
echo "=== FINAL STATE CHECK ==="
docker compose exec postgres psql -U postgres -d product_tracker -c "SELECT id, name, crawl_state, is_crawling FROM websites ORDER BY id;"
echo ""

echo "=== Queue Status ==="
echo "scrape_queue:"
docker compose exec redis redis-cli LLEN scrape_queue
echo ""

echo "=== Active Tasks ==="
docker compose exec celery_worker_crawl celery -A celery_app.celery inspect active | grep -c "extract_product_details_batch" || echo "0"
echo ""

echo "✅ All tests completed!"

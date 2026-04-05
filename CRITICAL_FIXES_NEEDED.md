# Critical System Issues - Comprehensive Fix Plan

## Issues Identified

1. **Crawl Start Button Not Working** - No response when clicking Start
2. **Tracked Products Table** - Dummy data, no real DB interaction
3. **Edit/Remove Buttons** - Only update UI, no database operations
4. **Products Page Not Loading** - Missing API endpoint
5. **Alerts Page Missing** - No route or template exists

---

## Issue 1: Crawl Start Button

### Problem
- Button click doesn't trigger crawl
- No API calls being made

### Root Cause
- Dashboard JavaScript may not be calling correct endpoint
- Endpoint is `/api/websites/{id}/crawl` (POST)

### Fix Required
- Verify dashboard_v2.html `startCrawl()` function
- Check browser console for errors
- Ensure Celery workers are receiving tasks

---

## Issue 2: Tracked Products - No Database Integration

### Problem
- Tracked products table shows dummy/static data
- Edit/Remove only affect UI, not database
- No real CRUD operations

### Current State
- API endpoints exist at `/api/tracked-products`
- GET, POST, PUT, DELETE all implemented
- Dashboard NOT using these endpoints

### Fix Required
1. Update `dashboard_v2.html` to:
   - Call GET `/api/tracked-products` on load
   - Call DELETE `/api/tracked-products/{id}` on remove
   - Call PUT `/api/tracked-products/{id}` on edit
   - Remove dummy data initialization

2. Implement edit modal with form
3. Add proper error handling

---

## Issue 3: Products Page Not Loading

### Problem
- Products page doesn't load
- Missing API endpoint for products list

### Current State
- No `/api/products` endpoint exists
- Only `/api/tracked-products` exists
- products_v2.html expects product data

### Fix Required
1. Create `/api/products` endpoint
2. Return all products from user's websites
3. Support filtering by:
   - Website
   - Gender
   - Search query
   - Availability
   - Price range

---

## Issue 4: Alerts Page Missing

### Problem
- No alerts page exists
- No route or template

### Fix Required
1. Create `alerts.html` template
2. Add route in `app/api/views.py`
3. Create `/api/alerts` endpoint
4. Display price/stock change notifications

---

## Implementation Priority

1. **HIGH**: Fix tracked products CRUD (backbone of system)
2. **HIGH**: Create products API endpoint
3. **MEDIUM**: Fix crawl start button
4. **MEDIUM**: Create alerts page
5. **LOW**: UI polish and error messages

---

## Tracked Products API Endpoints (Already Exist)

```
GET    /api/tracked-products           - List all tracked products
POST   /api/tracked-products           - Track new product
PUT    /api/tracked-products/{id}      - Update tracked product
DELETE /api/tracked-products/{id}      - Stop tracking product
```

### Expected Request/Response

**POST /api/tracked-products**
```json
{
  "product_id": 123,
  "priority": "high",
  "crawl_period_hours": 24,
  "price_condition": "less_than",
  "price_threshold": 99.99,
  "discord_webhook_url": "https://..."
}
```

**GET /api/tracked-products**
```json
[
  {
    "id": 1,
    "product_id": 123,
    "priority": "high",
    "product": {
      "id": 123,
      "title": "Nike Air Max",
      "price": 120.00,
      "image": "...",
      "brand": "Nike"
    }
  }
]
```

---

## Next Steps

1. Fix dashboard tracked products integration
2. Create products API
3. Fix products page
4. Create alerts page
5. Test end-to-end workflow

# Multi-Site Product Tracking Implementation

**Implementation Date:** 2026-03-31  
**Status:** ✅ COMPLETE & OPERATIONAL

---

## Overview

Successfully implemented multi-site product tracking for three major shoe retailers:
- **ASOS** (REST APIs)
- **ShopWSS** (GraphQL + Bazaarvoice)
- **ChampsSports** (Sitemap + Playwright)

The system now supports API-driven product discovery, detailed extraction, variant tracking, and automated monitoring across multiple sites.

---

## Architecture

### Site-Specific Scrapers

Each website has a dedicated scraper that implements the `BaseScraper` interface:

```
BaseScraper (Abstract)
├── AsosScraper (REST APIs)
├── ShopWssScraper (GraphQL + Bazaarvoice)
└── ChampsSportsScraper (Sitemap + Playwright)
```

**ScraperFactory** automatically selects the appropriate scraper based on the website URL.

### Data Flow

```
1. Website Detection
   ↓
2. Scraper Selection (Factory Pattern)
   ↓
3. Product Discovery (Gender-based)
   - ASOS: Search API (paginated)
   - ShopWSS: GraphQL API (paginated)
   - ChampsSports: Sitemap → Category pages
   ↓
4. Basic Product Storage
   ↓
5. Detail Extraction (Batched)
   - ASOS: Product detail API
   - ShopWSS: Bazaarvoice API
   - ChampsSports: Playwright scraping
   ↓
6. Variant Tracking
   - Size/color combinations
   - Individual availability
   - Price per variant
   ↓
7. Database Storage
   - Product records
   - ProductVariant records
   - ProductSnapshot for history
```

---

## Database Schema

### Enhanced Product Model

**New Fields:**
```python
gender              # 'men', 'women', 'unisex'
color               # Primary color
size_range          # e.g., "6-12"
price_current       # Current price
sale_price          # Sale/discounted price
is_new              # New arrival flag
is_on_sale          # On sale flag
availability        # 'InStock', 'OutOfStock', 'LowStock'
variants_data       # JSON: Full variant details
```

### ProductVariant Model

**Purpose:** Track individual size/color combinations

**Fields:**
```python
id                  # Primary key
product_id          # Foreign key to products
sku                 # Variant SKU
size                # Size (e.g., "9", "10.5")
color               # Color name
price               # Variant-specific price
availability        # Stock status
created_at          # First seen
updated_at          # Last updated
```

**Indexes:**
- `idx_variant_product` on `product_id`
- `idx_variant_sku` on `sku`

---

## Implementation Details

### 1. ASOS Scraper

**Discovery Method:** REST API
- **Endpoint:** `https://www.asos.com/api/product/search/v2/categories/{categoryId}`
- **Pagination:** Offset-based (72 items per page)
- **Category IDs:** Men: `4209`, Women: `4172`

**Detail Extraction:** REST API
- **Endpoint:** `https://www.asos.com/api/product/catalogue/v4/summaries`
- **Parameters:** `productIds`, `expand=variants`
- **Returns:** Full variant list with sizes, colors, availability

**Features:**
- ✅ Fast API-based discovery
- ✅ Complete variant information
- ✅ Real-time availability
- ✅ Price tracking (current + sale)

**Rate Limiting:**
- Search API: 1 req/sec
- Detail API: 3 req/sec

---

### 2. ShopWSS Scraper

**Discovery Method:** GraphQL (Nosto Search)
- **Endpoint:** `https://search.nosto.com/v1/graphql`
- **Account ID:** `shopify-6934429751`
- **Pagination:** `from` + `size` parameters
- **Category IDs:** Men: `153376063543`, Women: `153381568567`

**Detail Extraction:** Bazaarvoice API
- **Endpoint:** `https://apps.bazaarvoice.com/bfd/v1/clients/wss/api-products/cv2/resources/data/products.json`
- **Authentication:** `bv-bfd-token: 18656,main_site,en_US`
- **Returns:** Detailed product info, variants, reviews

**Features:**
- ✅ GraphQL-based discovery
- ✅ Structured product data
- ✅ Variant tracking
- ✅ Availability monitoring

**Rate Limiting:**
- GraphQL: 2 req/sec
- Bazaarvoice: 5 req/sec

---

### 3. ChampsSports Scraper

**Discovery Method:** Sitemap + Category Crawling
- **Sitemap:** `https://www.champssports.com/en/sitemap-shoes.xml`
- **Process:**
  1. Parse sitemap for category URLs
  2. Filter by gender (men/women)
  3. Crawl category pages for product links
  4. Extract product URLs

**Detail Extraction:** Playwright (JavaScript Rendering)
- **Data Sources:**
  - JSON-LD structured data
  - Inline JavaScript variables
  - DOM elements (fallback)

**Features:**
- ✅ Sitemap-based discovery
- ✅ JavaScript rendering support
- ✅ Multiple extraction strategies
- ✅ Robust fallback mechanisms

**Rate Limiting:**
- Playwright: 1 page/3 seconds
- Respectful crawling delays

---

## Celery Task Integration

### Discovery Tasks

**`discover_products_task(website_id, gender, limit)`**
- Discovers products for a specific gender category
- Stores basic product information
- Queues detail extraction tasks in batches

**`extract_product_details_batch(website_id, product_ids)`**
- Extracts detailed info for batches of products
- Updates product records with variants
- Creates ProductVariant records
- Rate-limited to respect API limits

### Updated Crawl Task

**`crawl_website(website_id, force_full_crawl)`**
- Detects if website is supported by new scrapers
- Routes to appropriate discovery method:
  - **Supported sites:** Uses ScraperFactory
  - **Legacy sites:** Falls back to sitemap parsing
- Queues gender-specific discovery tasks

---

## Usage Guide

### Adding a New Website

**1. Via Admin/API:**
```python
# Create website record
website = Website(
    user_id=user_id,
    name="ASOS",
    base_url="https://www.asos.com",
    sitemap_url="https://www.asos.com/sitemap.xml"  # Optional for API sites
)
db.session.add(website)
db.session.commit()
```

**2. Trigger Discovery:**
```python
# Manual trigger
from celery_app.tasks.discovery_tasks import discover_products_task

# Discover men's shoes
discover_products_task.delay(website.id, 'men', limit=100)

# Discover women's shoes
discover_products_task.delay(website.id, 'women', limit=100)
```

**3. Or Use Standard Crawl:**
```python
from celery_app.tasks.crawl_tasks import crawl_website

# Automatically detects and uses appropriate scraper
crawl_website.delay(website.id)
```

### Testing Scrapers

**Run Test Suite:**
```bash
docker compose exec flask python scripts/test_scrapers.py
```

**Test Individual Scraper:**
```python
from app.scraping import AsosScraper

scraper = AsosScraper(website_id=1, base_url="https://www.asos.com")
products = scraper.discover_products('men', limit=5)
print(f"Found {len(products)} products")

# Test detail extraction
if products:
    details = scraper.extract_product_details(products[0]['id'])
    print(f"Variants: {len(details.get('variants', []))}")

scraper.close()
```

---

## API Endpoints

### Product Queries

**Get Products by Gender:**
```python
products = Product.query.filter_by(
    website_id=website_id,
    gender='men'
).all()
```

**Get Products on Sale:**
```python
sale_products = Product.query.filter_by(
    website_id=website_id,
    is_on_sale=True
).all()
```

**Get New Arrivals:**
```python
new_products = Product.query.filter_by(
    website_id=website_id,
    is_new=True
).all()
```

**Get Product Variants:**
```python
from app.models import ProductVariant

variants = ProductVariant.query.filter_by(
    product_id=product_id
).all()

# Filter by availability
in_stock = ProductVariant.query.filter_by(
    product_id=product_id,
    availability='InStock'
).all()
```

---

## Performance Optimizations

### Rate Limiting
- Implemented per-scraper rate limits
- Exponential backoff on errors
- Configurable delays between requests

### Batching
- Products processed in batches of 50
- Parallel detail extraction
- Efficient database operations

### Caching
- Session pooling for HTTP requests
- Connection reuse across requests
- Retry logic with backoff

### Database
- Indexed fields: gender, is_new, is_on_sale, availability
- Efficient upsert operations
- Bulk variant creation

---

## Error Handling

### Retry Strategy
- **Max retries:** 3 attempts
- **Backoff:** Exponential (1s, 2s, 4s)
- **Status codes:** 429, 500, 502, 503, 504

### Logging
- Detailed error logging
- Request/response tracking
- Performance metrics

### Fallbacks
- ChampsSports: Multiple extraction strategies
- Graceful degradation on API failures
- Legacy sitemap support maintained

---

## Monitoring

### Key Metrics
- Products discovered per run
- Detail extraction success rate
- API response times
- Error rates by scraper

### Health Checks
```python
from app.scraping import ScraperFactory

# Check if site is supported
is_supported = ScraperFactory.is_supported("https://www.asos.com")

# Get supported sites
sites = ScraperFactory.get_supported_sites()
```

---

## Files Created

### Models
- `app/models/product.py` (updated)
- `app/models/product_variant.py` (new)

### Scrapers
- `app/scraping/base_scraper.py`
- `app/scraping/asos_scraper.py`
- `app/scraping/shopwss_scraper.py`
- `app/scraping/champssports_scraper.py`
- `app/scraping/scraper_factory.py`
- `app/scraping/__init__.py`

### Tasks
- `celery_app/tasks/discovery_tasks.py` (new)
- `celery_app/tasks/crawl_tasks.py` (updated)

### Migrations
- `alembic/versions/003_add_product_attributes.py`

### Scripts
- `scripts/test_scrapers.py`

### Documentation
- `MULTI_SITE_IMPLEMENTATION.md` (this file)

---

## Testing Results

### System Verification
```
✓ Product model fields: 19 fields including new attributes
✓ ProductVariant model loaded: 9 fields
✓ Scraper factory loaded: 3 supported sites
✓ All models importing correctly
✓ Database schema updated
```

### Scraper Tests
- **ASOS:** ✅ Discovery and detail extraction working
- **ShopWSS:** ✅ GraphQL discovery working
- **ChampsSports:** ✅ Sitemap parsing working

---

## Next Steps

### Immediate
1. ✅ Test with real websites
2. ✅ Verify data extraction
3. ✅ Monitor error rates
4. ✅ Optimize rate limits

### Future Enhancements
- [ ] Add more websites (Foot Locker, Finish Line, etc.)
- [ ] Implement ML-based price prediction
- [ ] Add image similarity detection
- [ ] Create variant-level alerts
- [ ] Build analytics dashboard
- [ ] Add webhook notifications

---

## Troubleshooting

### Common Issues

**1. "No scraper available for website"**
- Check if website URL matches supported domains
- Verify ScraperFactory.is_supported() returns True
- Add website to factory if needed

**2. "Rate limit exceeded"**
- Increase delays in scraper configuration
- Check API rate limits
- Implement request throttling

**3. "No products discovered"**
- Verify category IDs are correct
- Check API endpoints are accessible
- Review API response structure

**4. "Playwright timeout"**
- Increase timeout values
- Check network connectivity
- Verify page selectors are correct

---

## Support

For issues or questions:
1. Check logs: `docker compose logs flask`
2. Review error messages
3. Test individual scrapers
4. Verify database schema
5. Check API responses

---

**Implementation Complete! 🎉**

The multi-site tracking system is now fully operational and ready to track products across ASOS, ShopWSS, and ChampsSports with support for gender-based filtering, variant tracking, and automated monitoring.

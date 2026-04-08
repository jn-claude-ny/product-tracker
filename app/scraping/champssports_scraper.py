"""
champssports_scraper.py
-----------------------
Scraper for champssports.com. Has two separate responsibilities:

  1. extract_product_details(url)  [ACTIVE - used by scrape_tasks.py]
     ---------------------------------------------------------------
     Fetches a single Product Detail Page (PDP) HTML via BrightData residential
     proxy using the standard `requests` library. Parses the "sizes":[...] JSON
     array that is server-side rendered into the page HTML, and returns variant
     data (size, price, availability, inventory) for alert evaluation.

     Why `requests` and not Chrome:
       The PDP is SSR (server-side rendered). Bot detection does NOT apply to
       the PDP HTML fetch when going through BrightData — the proxy handles
       IP rotation and TLS fingerprint masking.

  2. discover_products(gender)  [ACTIVE - BrightData SSR]
     --------------------------------------------------
     Fetches ChampsSports category pages (e.g. /category/mens/shoes.html?start=0&sz=48)
     via BrightData residential proxy using `requests`. ChampsSports is a Next.js app
     so every page includes a <script id="__NEXT_DATA__"> block with the full page
     props as JSON. The product list is extracted from that JSON, same technique as
     extract_product_details. Pages are iterated by incrementing ?start=N until fewer
     than 48 products are returned (last page).

     Previously this used zendriver (undetected Chrome) + GOST proxy to intercept the
     search API, but Akamai Bot Manager blocked React hydration permanently disabling
     the Next button. The SSR HTML approach bypasses bot detection entirely.

PROXY (used by extract_product_details):
  BrightData residential proxy via environment variables:
    BRIGHTDATA_PROXY_HOST     default: brd.superproxy.io
    BRIGHTDATA_PROXY_PORT     default: 33335
    BRIGHTDATA_PROXY_USERNAME default: brd-customer-hl_b82fa24b-zone-wss_champs_asos-country-us
    BRIGHTDATA_PROXY_PASSWORD default: hppx772t42sn

DATA LOCATION IN PDP HTML:
  The page embeds product data in a <script> block as:
    "sizes":[{id, size, price.salePrice, inventory.inventoryAvailable, inventory.inventoryQuantity, ...}]
  The bracket-counting parser (not regex) is used because the sizes array
  contains deeply nested objects and a simple `.*?` regex stops at the first
  inner `]`, producing a truncated/invalid JSON string.
"""
import json
import logging
import os
import re
import time
from typing import List, Dict, Optional

from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ChampsSportsScraper(BaseScraper):
    """Scraper for champssports.com. Uses BrightData residential proxy + requests for both
    category page discovery (SSR __NEXT_DATA__ parsing) and PDP detail extraction."""

    def __init__(self, website_id: int, base_url: str = "https://www.champssports.com"):
        super().__init__(website_id, base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products by fetching ChampsSports category pages via BrightData proxy
        and parsing the STATE_FROM_SERVER JSON embedded in the SSR HTML.

        ChampsSports SSR-embeds all search state in a JS object literal:
            window.footlocker = { STATE_FROM_SERVER: { api: { ... } }, ... }

        STATE_FROM_SERVER is valid JSON and contains the search result at:
            api -> <search key> -> products (list) + pagination (totalPages, totalResults)

        This replaces the old zendriver/GOST approach which was broken by Akamai bot
        detection blocking React hydration and keeping the Next button permanently disabled.

        Pagination: ?start=N&sz=48 is incremented by 48 per page until totalPages is reached.
        """
        import requests as req

        proxy_host = os.getenv('BRIGHTDATA_PROXY_HOST', 'brd.superproxy.io')
        proxy_port = os.getenv('BRIGHTDATA_PROXY_PORT', '33335')
        proxy_user = os.getenv('BRIGHTDATA_PROXY_USERNAME', 'brd-customer-hl_b82fa24b-zone-wss_champs_asos-country-us')
        proxy_pass = os.getenv('BRIGHTDATA_PROXY_PASSWORD', 'hppx772t42sn')
        proxies = {
            'http':  f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
            'https': f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        category_path = "mens" if gender.lower() == "men" else "womens"
        base_url = f"https://www.champssports.com/category/{category_path}/shoes.html"
        page_size = 48
        all_products: List[Dict] = []
        start = 0

        logger.info(f"Starting ChampsSports discovery for gender={gender} via BrightData SSR")

        while True:
            if limit and len(all_products) >= limit:
                break

            url = f"{base_url}?start={start}&sz={page_size}"
            logger.info(f"Fetching ChampsSports category page: {url}")

            try:
                resp = req.get(url, headers=headers, proxies=proxies, timeout=45, verify=False)
                resp.raise_for_status()
            except Exception as e:
                logger.error(f"ChampsSports category fetch failed at start={start}: {e}")
                break

            html = resp.text

            # Extract products from window.footlocker.STATE_FROM_SERVER
            products_raw, pagination = self._extract_from_state(html)
            if not products_raw:
                logger.warning(f"No products found at start={start} — bot block or structure changed")
                break

            total_pages = pagination.get('totalPages', 1) if pagination else 1
            total_results = pagination.get('totalResults', '?') if pagination else '?'

            all_products.extend(products_raw)
            logger.info(
                f"Page start={start}: got {len(products_raw)} products "
                f"(total so far: {len(all_products)}, site total: {total_results})"
            )

            if len(products_raw) < page_size or (start // page_size) + 1 >= total_pages:
                logger.info("Last page reached")
                break

            start += page_size
            time.sleep(1.5)  # polite delay between pages

        if limit:
            all_products = all_products[:limit]

        logger.info(f"ChampsSports discovery complete: {len(all_products)} raw products")
        return self._normalize_discovered_products(all_products, gender)

    def _extract_from_state(self, html: str):
        """
        Extract the product list and pagination from ChampsSports category page HTML.

        ChampsSports embeds its Redux/React state in a JS object literal:
            window.footlocker = { STATE_FROM_SERVER: { ... }, ... }

        STATE_FROM_SERVER is valid JSON and contains the full search result under:
            api -> (some key with 'search' in it) -> products / pagination

        Returns (products: List[Dict], pagination: dict | None)
        """
        match = re.search(r'STATE_FROM_SERVER\s*:\s*(\{)', html)
        if not match:
            logger.warning("STATE_FROM_SERVER not found in HTML — possible bot block")
            return [], None

        start = match.start(1)
        depth = 0
        end = start
        for i, ch in enumerate(html[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break

        try:
            sfs = json.loads(html[start:end])
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse STATE_FROM_SERVER JSON: {e}")
            return [], None

        # Products live inside sfs.api.<search-key>.products
        # Walk recursively — the key name changes per deployment
        products = self._find_key(sfs, 'products')
        pagination = self._find_key(sfs, 'pagination')
        return (products or []), pagination

    def _find_key(self, obj, key: str, depth: int = 0):
        """Recursively find the first value for a given key in a nested dict/list."""
        if depth > 15:
            return None
        if isinstance(obj, dict):
            if key in obj:
                return obj[key]
            for v in obj.values():
                result = self._find_key(v, key, depth + 1)
                if result is not None:
                    return result
        elif isinstance(obj, list):
            for item in obj:
                result = self._find_key(item, key, depth + 1)
                if result is not None:
                    return result
        return None

    def extract_product_details(self, url: str) -> Optional[Dict]:
        """
        Fetch the Product Detail Page (PDP) HTML and extract size/variant data.

        Args:
            url: Full product URL, e.g.
                 https://www.champssports.com/product/asics-gel-1130-mens/3A609021.html

        Returns dict with keys:
            variants      - list of {sku, size, price, available, availability, inventoryLevel}
            availability  - 'InStock' or 'OutOfStock' (derived from variants)
            available     - bool
            inventoryLevel - total inventory across all variants
            price         - price from first available variant
        """
        import requests as req

        # Guard: if a bare SKU was stored in product.url (legacy data from the old broken
        # zendriver scraper), reconstruct the full PDP URL from the SKU.
        if not url.startswith('http'):
            sku = url
            url = f"https://www.champssports.com/product/~/~/{sku}.html"
            logger.info(f"Reconstructed Champs PDP URL from bare SKU: {url}")

        # Read BrightData proxy credentials from environment (set in docker-compose / .env)
        proxy_host = os.getenv('BRIGHTDATA_PROXY_HOST', 'brd.superproxy.io')
        proxy_port = os.getenv('BRIGHTDATA_PROXY_PORT', '33335')
        proxy_user = os.getenv('BRIGHTDATA_PROXY_USERNAME', 'brd-customer-hl_b82fa24b-zone-wss_champs_asos-country-us')
        proxy_pass = os.getenv('BRIGHTDATA_PROXY_PASSWORD', 'hppx772t42sn')
        proxies = {
            'http':  f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
            'https': f'http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}',
        }
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
        }

        try:
            resp = req.get(url, headers=headers, proxies=proxies, timeout=30, verify=False)
            resp.raise_for_status()
        except Exception as e:
            logger.error(f'ChampsSports PDP fetch failed for {url}: {e}')
            return None

        html = resp.text

        # ---------------------------------------------------------------------------
        # EXTRACT "sizes":[...] FROM PAGE HTML
        # ---------------------------------------------------------------------------
        # The page embeds all size/variant data in a JS variable inside a <script>
        # block as:  "sizes":[{...}, {...}, ...]
        #
        # WHY bracket-counting instead of regex:
        #   re.DOTALL + .*? stops at the FIRST ] it finds, which may be inside a
        #   nested object (e.g. inside inventory.storeUpc array), producing a
        #   truncated string that fails JSON parsing.
        #   The bracket counter correctly walks to the matching closing ] at
        #   depth 0, regardless of nesting.
        # ---------------------------------------------------------------------------
        start_match = re.search(r'"sizes"\s*:\s*\[', html)
        if not start_match:
            logger.warning(f'No sizes data found in ChampsSports PDP: {url}')
            return None

        start = start_match.end() - 1  # position of the opening '['
        depth = 0
        end = start
        for i, ch in enumerate(html[start:], start):
            if ch == '[':
                depth += 1
            elif ch == ']':
                depth -= 1
                if depth == 0:
                    end = i + 1  # include the closing ']'
                    break

        try:
            sizes_raw = json.loads(html[start:end])
        except json.JSONDecodeError as e:
            logger.error(f'Failed to parse sizes JSON: {e}')
            return None

        variants = []
        any_in_stock = False
        total_inv = 0
        for s in sizes_raw:
            try:
                inv = s.get('inventory', {})
                available = bool(inv.get('inventoryAvailable', False))
                inv_qty = int(inv.get('inventoryQuantity') or 0)
                price_info = s.get('price', {})
                price_val = price_info.get('salePrice') or price_info.get('formattedSalePrice')
                if isinstance(price_val, str):
                    price_val = float(re.sub(r'[^\d.]', '', price_val)) if price_val else None

                variants.append({
                    'sku': str(s.get('id') or s.get('sku', '')),
                    'size': str(s.get('size') or s.get('value', '')),
                    'color': None,
                    'price': price_val,
                    'available': available,
                    'availability': 'InStock' if available else 'OutOfStock',
                    'inventoryLevel': inv_qty,
                })
                if available:
                    any_in_stock = True
                total_inv += inv_qty
            except Exception as e:
                logger.warning(f'Error parsing size entry: {e}')
                continue

        if not variants:
            return None

        # Extract product-level price from first variant or page meta
        price = next((v['price'] for v in variants if v['price']), None)

        return {
            'variants': variants,
            'availability': 'InStock' if any_in_stock else 'OutOfStock',
            'available': any_in_stock,
            'inventoryLevel': total_inv if total_inv > 0 else None,
            'price': price,
        }

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_discovered_products(self, products: List[Dict], gender: str) -> List[Dict]:
        """Normalize API response products to standard format.

        The zgw/search-core API returns one entry per colorway with its own SKU,
        so no expansion needed — each entry IS a unique colorway.
        """
        normalized = []
        seen_skus: set = set()

        for product in products:
            try:
                sku = product.get('sku') or product.get('id') or product.get('productId')
                if not sku or sku in seen_skus:
                    continue
                seen_skus.add(sku)

                name = product.get('name') or product.get('title', '')
                brand = product.get('brand') or product.get('brandName') or self._extract_brand_from_name(name)

                # Price
                price_current = None
                price_data = product.get('price', {})
                if isinstance(price_data, dict):
                    price_current = price_data.get('salePrice') or price_data.get('value')
                elif isinstance(price_data, (int, float)):
                    price_current = float(price_data)

                # Sale flag
                is_on_sale = product.get('isOnSale', False) or product.get('isSale', False)
                if not is_on_sale:
                    orig = product.get('originalPrice', {})
                    if isinstance(orig, dict) and orig.get('value') and price_current:
                        is_on_sale = price_current < orig['value']

                # Image
                image = product.get('thumbnail') or product.get('imageUrl')
                if not image:
                    images = product.get('images', [])
                    if isinstance(images, list) and images:
                        large = next(
                            (img.get('url') for img in images
                             if isinstance(img, dict) and img.get('format') == 'large'),
                            None
                        )
                        image = large or (images[0].get('url') if isinstance(images[0], dict) else None)

                # Color
                color = product.get('color') or product.get('style')
                if not color:
                    base_options = product.get('baseOptions', [])
                    if isinstance(base_options, list) and base_options:
                        selected = base_options[0].get('selected', {})
                        if isinstance(selected, dict):
                            color = selected.get('style')

                # URL — STATE_FROM_SERVER may return a relative path; make it absolute
                url = product.get('url') or ''
                if url and not url.startswith('http'):
                    url = f"https://www.champssports.com{url}"
                if not url:
                    url = self._build_product_url(product)

                normalized.append({
                    'sku': sku,
                    'title': name,
                    'brand': brand,
                    'url': url,
                    'image': image,
                    'gender': gender,
                    'category': product.get('category'),
                    'color': color,
                    'price_current': price_current,
                    'is_on_sale': is_on_sale,
                    'is_new': product.get('isNew', False) or product.get('isNewProduct', False),
                })

            except Exception as e:
                logger.warning(f"Error normalizing product: {e}")
                continue

        return normalized

    def _extract_brand_from_name(self, name: str) -> Optional[str]:
        """Extract brand from product name."""
        known_brands = [
            'Nike', 'Jordan', 'adidas', 'New Balance', 'ASICS', 'Puma', 'Reebok',
            'Converse', 'Vans', 'Under Armour', 'Saucony', 'Brooks', 'Hoka',
            'Timberland', 'UGG', 'Champion', 'Fila', 'Lacoste', 'Crocs',
        ]
        if not name:
            return None
        for brand in known_brands:
            if name.lower().startswith(brand.lower()):
                return brand
        return name.split(' ')[0] if name else None

    def _build_product_url(self, product: Dict) -> str:
        """Build product URL from name + SKU."""
        try:
            name = product.get('name', '')
            sku = product.get('sku', '')
            if name and sku:
                slug = name.lower()
                slug = slug.encode('ascii', 'ignore').decode('ascii')
                slug = re.sub(r'[^a-z0-9\s-]', '', slug)
                slug = re.sub(r'\s+', '-', slug.strip())
                slug = re.sub(r'-+', '-', slug)
                return f"https://www.champssports.com/product/~/{slug}/{sku}.html"
        except Exception:
            pass
        return f"https://www.champssports.com/product/~/~/{product.get('sku', '')}.html"

    def normalize_product_data(self, raw_data: Dict, gender: str) -> Dict:
        """Pass-through — products are already normalized by _normalize_discovered_products."""
        return {
            'sku': raw_data.get('sku'),
            'title': raw_data.get('title'),
            'brand': raw_data.get('brand'),
            'url': raw_data.get('url'),
            'image': raw_data.get('image'),
            'gender': gender,
            'category': raw_data.get('category'),
            'color': raw_data.get('color'),
            'price_current': raw_data.get('price_current'),
            'currency': raw_data.get('currency', 'USD'),
            'is_on_sale': raw_data.get('is_on_sale', False),
            'is_new': raw_data.get('is_new', False),
            'categories': raw_data.get('categories', []),
            'availability': raw_data.get('availability'),
            'available': raw_data.get('available'),
            'inventoryLevel': raw_data.get('inventoryLevel'),
        }

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

  2. discover_products(gender)  [LEGACY/BROKEN - zendriver + GOST]
     ------------------------------------------------------------
     Originally used zendriver (undetected Chrome) + a local GOST proxy tunnel
     to intercept the search API (zgw/search-core/products/v3/search) via CDP.
     THIS IS NOT CURRENTLY WORKING due to Akamai Bot Manager blocking React
     hydration, which keeps the Next-page button permanently disabled even with
     a real browser. Kept in code for future reference.

     If you need to fix discovery, the options are:
       a) BrightData Scraping Browser (proxy with built-in bot bypass)
       b) Playwright + stealth plugin
       c) Parse the SSR HTML on the category page (same approach as PDP)

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
import asyncio
import base64
import json
import logging
import os
import re
import subprocess
import time
from typing import List, Dict, Optional

# zendriver is only installed in the worker container (not Flask).
# Guard the import so the Flask container doesn't crash on startup.
# discover_products() uses zendriver; extract_product_details() does NOT.
try:
    import zendriver as zd
    from zendriver.core.config import Config
    from zendriver.cdp.network import get_response_body
except ImportError:
    zd = None
    Config = None
    get_response_body = None

from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration for the legacy zendriver-based discovery (currently unused)
# ---------------------------------------------------------------------------
CHROME_EXE   = os.getenv('CHROME_EXECUTABLE_PATH', '/usr/bin/google-chrome-stable')
PROFILE_DIR  = os.getenv('CHAMPS_USER_DATA_DIR', '/app/app/scraping/champ_data_linux')
GOST_PORT    = int(os.getenv('CHAMPS_GOST_PORT', '18899'))      # local GOST HTTP proxy port
GOST_EXE     = os.getenv('GOST_EXECUTABLE', '/usr/local/bin/gost')
PROXY_HOST   = os.getenv('CHAMPS_PROXY_HOST', 'brd.superproxy.io:33335')
PROXY_USER   = os.getenv('CHAMPS_PROXY_USER', 'brd-customer-hl_752541f5-zone-champs_residential_proxy1')
PROXY_PASS   = os.getenv('CHAMPS_PROXY_PASS', 'zk7h5o7vxvt3')
XDISPLAY     = os.getenv('CHAMPS_DISPLAY', ':89')  # virtual X display for Xvfb


class ChampsSportsScraper(BaseScraper):
    """Scraper for champssports.com using zendriver + GOST proxy tunnel."""

    def __init__(self, website_id: int, base_url: str = "https://www.champssports.com"):
        super().__init__(website_id, base_url)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """Discover products using zendriver to intercept the search API."""
        try:
            return asyncio.run(self._discover_async(gender, limit))
        except Exception as e:
            logger.error(f"discover_products failed: {e}", exc_info=True)
            return []

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
    # Async discovery
    # ------------------------------------------------------------------

    def _start_xvfb(self) -> Optional[subprocess.Popen]:
        """Start a virtual X display so Chrome can run non-headlessly."""
        lock = f"/tmp/.X{XDISPLAY.lstrip(':')}-lock"
        try:
            os.remove(lock)
        except FileNotFoundError:
            pass
        proc = subprocess.Popen(
            ['Xvfb', XDISPLAY, '-screen', '0', '1280x800x24', '-ac'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        os.environ['DISPLAY'] = XDISPLAY
        logger.info(f"Xvfb started on {XDISPLAY}")
        return proc

    def _start_gost(self) -> subprocess.Popen:
        """Start a local GOST tunnel and pre-warm it with a test request."""
        proxy_url = f"http://{PROXY_USER}:{PROXY_PASS}@{PROXY_HOST}"
        proc = subprocess.Popen(
            [GOST_EXE, '-L', f'http://:{GOST_PORT}', '-F', proxy_url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        time.sleep(1.5)
        logger.info(f"GOST proxy tunnel started on port {GOST_PORT}")

        # Pre-warm: the first CONNECT through a residential proxy often returns 503.
        # Fire a throwaway request so Chrome's first navigation hits a warm tunnel.
        import ssl, urllib.request
        proxy_handler = urllib.request.ProxyHandler({
            'https': f'http://127.0.0.1:{GOST_PORT}',
            'http':  f'http://127.0.0.1:{GOST_PORT}',
        })
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        opener = urllib.request.build_opener(proxy_handler, urllib.request.HTTPSHandler(context=ctx))
        for attempt in range(5):
            try:
                opener.open('https://www.champssports.com', timeout=10).read(100)
                logger.info(f"GOST tunnel warmed up (attempt {attempt+1})")
                break
            except Exception as e:
                logger.debug(f"GOST warmup attempt {attempt+1}: {e}")
                time.sleep(1)
        return proc

    async def _click_and_capture(self, tab, btn) -> Optional[Dict]:
        """Click a next-page button and capture the search API response."""
        captured: Dict = {}
        done = asyncio.Event()

        async def on_response(event):
            try:
                url = event.response.url if hasattr(event, 'response') else ''
                if 'zgw/search-core/products/v3/search' in url:
                    captured['request_id'] = event.request_id
                    done.set()
            except Exception:
                pass

        tab.add_handler(zd.cdp.network.ResponseReceived, on_response)
        try:
            await btn.click()
            try:
                await asyncio.wait_for(done.wait(), timeout=20)
            except asyncio.TimeoutError:
                logger.warning("Timed out waiting for search API response")
                return None

            request_id = captured.get('request_id')
            if not request_id:
                return None

            # Small buffer to ensure body is fully received
            await asyncio.sleep(0.5)
            try:
                body, is_base64 = await tab.send(get_response_body(request_id=request_id))
                if is_base64:
                    body = base64.b64decode(body).decode('utf-8')
                return json.loads(body)
            except Exception as e:
                logger.error(f"get_response_body failed: {e}")
                return None
        finally:
            tab.remove_handlers(zd.cdp.network.ResponseReceived)

    async def _discover_async(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        logger.info(f"Starting ChampsSports discovery for gender={gender}")

        category_path = "mens" if gender.lower() == "men" else "womens"
        category_url = f"https://www.champssports.com/category/{category_path}/shoes.html"

        xvfb_proc = self._start_xvfb()
        gost_proc = self._start_gost()
        all_raw: List[Dict] = []

        # Clear Chrome singleton locks so the profile can be reused
        for fname in ('SingletonLock', 'SingletonSocket', 'SingletonCookie'):
            try:
                os.remove(os.path.join(PROFILE_DIR, fname))
            except FileNotFoundError:
                pass

        try:
            cfg = Config(
                browser_executable_path=CHROME_EXE,
                user_data_dir=PROFILE_DIR,
                sandbox=False,
                headless=False,
                browser_args=[
                    f'--proxy-server=http://127.0.0.1:{GOST_PORT}',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--ignore-certificate-errors',
                ],
            )
            cfg.browser_connection_timeout = 1.0
            cfg.browser_connection_max_tries = 20
            browser = await zd.Browser.create(cfg)
            tab = browser.main_tab

            try:
                await tab.send(zd.cdp.network.enable())

                # Establish session via homepage first
                logger.info("Establishing session via homepage...")
                for attempt in range(3):
                    await tab.get("https://www.champssports.com")
                    await asyncio.sleep(5)
                    hp_title = await tab.evaluate("document.title")
                    if hp_title and hp_title != 'www.champssports.com':
                        break
                    logger.warning(f"Homepage attempt {attempt+1} failed (title={hp_title!r}), retrying...")
                    await asyncio.sleep(3)
                logger.info(f"Homepage title: {hp_title!r}")

                logger.info("Loading category page...")
                await tab.get(category_url)
                await asyncio.sleep(8)

                title = await tab.evaluate("document.title")
                logger.info(f"Category page title: {title!r}")

                page_num = 0
                while True:
                    if limit and len(all_raw) >= limit:
                        break

                    logger.info(f"Processing page {page_num + 1}")

                    # button[aria-label='Next'] = React XHR pagination
                    # Must wait for it to be enabled (React hydration)
                    try:
                        next_btn = await tab.find("button[aria-label='Next']", timeout=15)
                    except asyncio.TimeoutError:
                        next_btn = None
                    if not next_btn:
                        logger.info("No Next button — reached last page")
                        break

                    # Wait for React to hydrate and enable the button
                    for _ in range(20):
                        disabled = await tab.evaluate(
                            "document.querySelector(\"button[aria-label='Next']\")?.disabled"
                        )
                        if not disabled:
                            break
                        await asyncio.sleep(0.5)
                    else:
                        logger.warning("Next button still disabled after 10s, trying anyway")
                    await asyncio.sleep(0.5)  # brief settle after hydration

                    data = await self._click_and_capture(tab, next_btn)
                    if data is None:
                        logger.error(f"No API data on page {page_num + 1}")
                        break

                    products = data.get('products', [])
                    if not products:
                        logger.info(f"No products on page {page_num + 1}, stopping")
                        break

                    all_raw.extend(products)
                    total = data.get('totalResults', '?')
                    logger.info(
                        f"Page {page_num + 1}: {len(products)} products "
                        f"(total so far: {len(all_raw)}, site total: {total})"
                    )
                    page_num += 1
                    await asyncio.sleep(2)

            except Exception as e:
                logger.error(f"Error during discovery: {e}", exc_info=True)
            finally:
                await browser.stop()

        finally:
            gost_proc.terminate()
            gost_proc.wait()
            xvfb_proc.terminate()
            xvfb_proc.wait()

        if limit:
            all_raw = all_raw[:limit]

        logger.info(f"Total raw products from API: {len(all_raw)}")
        return self._normalize_discovered_products(all_raw, gender)

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

                # URL
                url = product.get('url') or self._build_product_url(product)

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

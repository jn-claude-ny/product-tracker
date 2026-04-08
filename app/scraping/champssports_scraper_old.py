"""
ChampsSports Scraper
Handles product discovery and extraction from champssports.com via SSR HTML parsing.
"""
import json
import logging
import os
import re
from typing import List, Dict, Optional
from datetime import datetime
from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ChampsSportsScraper(BaseScraper):
    """Scraper for champssports.com using requests + SSR HTML parsing"""

    def __init__(self, website_id: int, base_url: str = "https://www.champssports.com"):
        super().__init__(website_id, base_url)
        proxy_host = os.getenv('BRIGHTDATA_PROXY_HOST', '')
        proxy_port = os.getenv('BRIGHTDATA_PROXY_PORT', '')
        proxy_user = os.getenv('BRIGHTDATA_PROXY_USERNAME', '')
        proxy_pass = os.getenv('BRIGHTDATA_PROXY_PASSWORD', '')
        self.proxies = {
            "server": f"http://{proxy_host}:{proxy_port}" if proxy_host and proxy_port else os.getenv('CHAMPS_PROXY_SERVER', ''),
            "username": proxy_user or os.getenv('CHAMPS_PROXY_USERNAME', ''),
            "password": proxy_pass or os.getenv('CHAMPS_PROXY_PASSWORD', ''),
        }

    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """Discover products by fetching SSR HTML and parsing ProductCard tiles."""
        try:
            return self._discover_products_via_html(gender, limit)
        except Exception as e:
            logger.error(f"Error in discover_products: {e}")
            import traceback; traceback.print_exc()
            return []

    def _make_session(self):
        """Build a requests.Session with proxy and browser-like headers."""
        import requests
        session = requests.Session()
        server = self.proxies.get('server', '')
        username = self.proxies.get('username', '')
        password = self.proxies.get('password', '')
        if server:
            if username and password:
                from urllib.parse import urlparse, urlunparse
                parsed = urlparse(server)
                proxy_url = urlunparse(parsed._replace(netloc=f'{username}:{password}@{parsed.netloc}'))
            else:
                proxy_url = server
            session.proxies = {'http': proxy_url, 'https': proxy_url}
        session.verify = False
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
        })
        return session

    # ------------------------------------------------------------------
    # HTML tile parsing
    # ------------------------------------------------------------------

    def _extract_total_pages(self, html: str) -> int:
        """Extract totalPages from STATE_FROM_SERVER JSON blob, fallback to 10."""
        m = re.search(r'"totalPages"\s*:\s*(\d+)', html)
        return int(m.group(1)) if m else 10

    def _parse_product_cards(self, html: str, gender: str) -> List[Dict]:
        """Parse ProductCard tiles from SSR HTML into normalized product dicts."""
        import html as _h
        products = []

        card_pattern = re.compile(
            r'<div class="ProductCard ProductCard--flexDirection ProductCardV3[^"]*">',
        )
        positions = [m.start() for m in card_pattern.finditer(html)]

        for idx, pos in enumerate(positions):
            # slice card: from this card start to next card start (or +15000 max)
            end = positions[idx + 1] if idx + 1 < len(positions) else pos + 15000
            card = html[pos:end]

            try:
                # URL + SKU from main product link href
                url_m = re.search(r'href="(/product/([^/]+)/([A-Z0-9]+)\.html)"', card)
                if not url_m:
                    continue
                path, slug, sku = url_m.group(1), url_m.group(2), url_m.group(3)
                product_url = "https://www.champssports.com" + path

                # Title
                title_m = re.search(r'class="ProductName-primary">([^<]+)<', card)
                title = _h.unescape(title_m.group(1).strip()) if title_m else slug.replace('-', ' ').title()

                # Color — text after the gender span inside ProductName-alt
                color = None
                alt_m = re.search(
                    r'class="ProductName-alt[^"]*">.*?'
                    r'<span class="ProductName-second[^"]*">[^<]*</span>(.*?)</span>',
                    card, re.DOTALL
                )
                if alt_m:
                    raw = re.sub(r'<[^>]+>', '', alt_m.group(1)).strip()
                    color = _h.unescape(raw) or None

                # Prices
                sale_m = re.search(r'class="font-medium text-sale_red"[^>]*>\$([0-9]+\.[0-9]+)<', card)
                reg_m  = re.search(r'class="font-normal text-footlocker_black line-through"[^>]*>\$([0-9]+\.[0-9]+)<', card)
                any_m  = re.search(r'>\$([0-9]+\.[0-9]+)<', card)
                price_current  = float(sale_m.group(1)) if sale_m else (float(any_m.group(1)) if any_m else None)
                original_price = float(reg_m.group(1)) if reg_m else None
                is_on_sale = bool(sale_m) or bool(
                    original_price and price_current and price_current < original_price
                )

                # Image (250px primary)
                img_m = re.search(r'class="ProductCard-image--primary[^"]*"[^>]*src="([^"]+)"', card)
                image = img_m.group(1).replace('&amp;', '&') if img_m else None

                # Badge → is_new
                badge_m = re.search(r'ProductCard-badge-mobile[^>]*>.*?<span[^>]*>([^<]+)<', card, re.DOTALL)
                badge = _h.unescape(badge_m.group(1).strip()) if badge_m else None
                is_new = bool(badge and 'new' in badge.lower())

                products.append({
                    'sku': sku,
                    'title': title,
                    'brand': self._extract_brand_from_name(title),
                    'url': product_url,
                    'image': image,
                    'gender': gender,
                    'category': 'shoes',
                    'color': color,
                    'price_current': price_current,
                    'is_on_sale': is_on_sale,
                    'is_new': is_new,
                })
            except Exception as e:
                logger.warning(f"Error parsing product card: {e}")

        return products

    def _discover_products_via_html(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """Fetch SSR HTML pages and parse ProductCard tiles for all pages."""
        import time as _time

        category_path = "mens" if gender.lower() == "men" else "womens"
        base_url = f"https://www.champssports.com/category/{category_path}/shoes.html"

        all_products: List[Dict] = []
        seen_skus: set = set()
        page_num = 0
        max_pages = 10

        while page_num < max_pages:
            if limit and len(all_products) >= limit:
                break

            # Always use ?currentPage=N (works for page 0 too).
            # Fresh session per page — each gets a new residential IP which
            # avoids the proxy zone's per-IP URL filtering.
            url = f"{base_url}?currentPage={page_num}"

            logger.info(f"Fetching page {page_num + 1}: {url}")
            resp = None

            # Try no-proxy first (no zone restrictions, no IP blacklisting).
            # Fall back to proxy if we get a geo-redirect (302 to footlocker.eu).
            for use_proxy in (False, True):
                session = self._make_session()
                if not use_proxy:
                    session.proxies = {}
                try:
                    resp = session.get(url, timeout=30, allow_redirects=False)
                    if resp.status_code in (301, 302, 303, 307, 308):
                        loc = resp.headers.get('Location', '')
                        if 'footlocker.eu' in loc or 'gdpr' in loc:
                            logger.info(f"Geo-redirect on page {page_num + 1}, retrying via proxy")
                            resp = None
                            continue
                    if resp.status_code in (402, 407, 502, 503):
                        resp = None
                        continue
                    resp.raise_for_status()
                    break
                except Exception as e:
                    logger.warning(f"Page {page_num + 1} ({'proxy' if use_proxy else 'direct'}) failed: {e}")
                    resp = None

            if resp is None or not resp.ok:
                logger.warning(f"All attempts failed on page {page_num + 1}, stopping")
                break

            html = resp.content.decode('utf-8', errors='replace')
            products = self._parse_product_cards(html, gender)

            if not products:
                logger.info(f"No product cards on page {page_num + 1}, stopping")
                break

            # Deduplicate — guards against CDN serving wrong cached page
            new_products = [p for p in products if p['sku'] not in seen_skus]
            if page_num > 0 and not new_products:
                logger.warning(f"Page {page_num + 1} all duplicate SKUs (CDN cache hit), stopping")
                break

            for p in new_products:
                seen_skus.add(p['sku'])
            all_products.extend(new_products)
            logger.info(f"Page {page_num + 1}: {len(new_products)} new products (total: {len(all_products)})")

            if page_num == 0:
                total_pages = self._extract_total_pages(html)
                if limit:
                    max_pages = min(total_pages, (limit + 47) // 48)
                else:
                    max_pages = total_pages
                logger.info(f"Total pages: {total_pages}, fetching up to: {max_pages}")

            page_num += 1
            if page_num < max_pages:
                _time.sleep(2.0)

        if limit:
            all_products = all_products[:limit]

        logger.info(f"Total products discovered: {len(all_products)}")
        return all_products

    # ------------------------------------------------------------------
    # Detail extraction (PDP)
    # ------------------------------------------------------------------

    def extract_product_details(self, product_url: str) -> Optional[Dict]:
        """Extract product details by fetching PDP HTML and parsing embedded sizes array."""
        try:
            session = self._make_session()
            resp = session.get(product_url, timeout=25)
            resp.raise_for_status()
            html = resp.content.decode('utf-8', errors='replace')

            m = re.search(r'"sizes"\s*:\s*(\[)', html)
            if not m:
                logger.warning(f"No sizes array found in PDP HTML for {product_url}")
                return None

            start = m.start(1)
            depth = 0
            end = start
            for i, ch in enumerate(html[start:], start):
                if ch == '[': depth += 1
                elif ch == ']':
                    depth -= 1
                    if depth == 0:
                        end = i + 1
                        break

            sizes = json.loads(html[start:end])
            return self._normalize_product_details({'sizes': sizes}, product_url)

        except Exception as e:
            logger.error(f"Error extracting ChampsSports product details: {e}")
            return None

    def _normalize_product_details(self, data: Dict, product_url: str) -> Dict:
        """Normalize detailed product data from PDP."""
        try:
            product = data.get('product', data)
            variants = []
            for size_entry in product.get('sizes', []):
                if not isinstance(size_entry, dict):
                    continue
                size = size_entry.get('size') or size_entry.get('strippedSize')
                price_data = size_entry.get('price', {})
                sale_price = price_data.get('salePrice') if isinstance(price_data, dict) else None
                inventory = size_entry.get('inventory', {})
                is_available = inventory.get('inventoryAvailable', False) if isinstance(inventory, dict) else False
                variant_sku = size_entry.get('id') or size_entry.get('productNumber')
                variants.append({
                    'sku': str(variant_sku) if variant_sku else None,
                    'size': str(size) if size else None,
                    'color': None,
                    'price': sale_price,
                    'available': is_available,
                    'availability': 'InStock' if is_available else 'OutOfStock',
                    'inventoryLevel': None,
                })

            return {
                'url': product_url,
                'sku': product.get('sku') or product.get('productId'),
                'title': product.get('name') or product.get('title'),
                'brand': product.get('brand') or product.get('brandName'),
                'image': product.get('image') or product.get('imageUrl'),
                'gender': product.get('gender'),
                'category': product.get('category'),
                'color': product.get('color'),
                'price_current': self._extract_price(product.get('price')),
                'is_on_sale': product.get('is_on_sale', False) or product.get('isOnSale', False),
                'is_new': product.get('is_new', False) or product.get('isNew', False),
                'availability': self._normalize_availability(product),
                'variants': variants,
                'detail_last_fetched': datetime.utcnow(),
            }

        except Exception as e:
            logger.error(f"Error normalizing product details: {e}")
            return {'url': product_url, 'detail_last_fetched': datetime.utcnow()}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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
        """Build product URL from API data."""
        try:
            if 'url' in product:
                return product['url']
            name = product.get('name', '')
            sku = product.get('sku', '')
            if name and sku:
                slug = name.lower().encode('ascii', 'ignore').decode('ascii')
                slug = re.sub(r'[^a-z0-9\s-]', '', slug)
                slug = re.sub(r'\s+', '-', slug.strip())
                slug = re.sub(r'-+', '-', slug)
                return f"https://www.champssports.com/product/{slug}/{sku}.html"
            return f"https://www.champssports.com/product/{sku}.html" if sku else ""
        except Exception as e:
            logger.warning(f"Error building product URL: {e}")
            return ""

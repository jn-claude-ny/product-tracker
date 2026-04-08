"""
ShopWSS Scraper
Handles product discovery and per-product refresh from shopwss.com using the Nosto GraphQL API.
All product data (including variants) is retrieved in a single GraphQL query — no secondary API needed.
"""
import logging
from typing import List, Dict, Optional
from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

# Discovery query — fetches full product + SKU/variant data in one shot
DISCOVERY_QUERY = (
    "query ( $accountId: String, $query: String, $products: InputSearchProducts,"
    " $categories: InputSearchCategories) {"
    " search( accountId: $accountId query: $query  products: $products categories: $categories) {"
    " query  products { hits { productId url name imageUrl brand variantId availability"
    " price priceCurrencyCode inventoryLevel"
    " skus { id name price inventoryLevel customFields { key value } availability  }"
    " } total size from } } }"
)

# Refresh query — fetches a single product by SKU keyword search
REFRESH_QUERY = (
    "query ( $accountId: String, $query: String, $products: InputSearchProducts ) {"
    " search( accountId: $accountId query: $query  products: $products ) {"
    " query products { hits { productId url name imageUrl brand availability price"
    " priceCurrencyCode inventoryLevel available"
    " skus { id name price url imageUrl inventoryLevel availability customFields { key value } } } } }}"
)


class ShopWssScraper(BaseScraper):
    """Scraper for shopwss.com using the Nosto GraphQL API"""

    CATEGORY_IDS = {
        'men': '153376063543',
        'women': '153381568567'
    }

    GRAPHQL_URL = "https://search.nosto.com/v1/graphql"
    ACCOUNT_ID = "shopify-6934429751"

    def __init__(self, website_id: int, base_url: str = "https://www.shopwss.com"):
        super().__init__(website_id, base_url)
        self.graphql_headers = {
            'Content-Type': 'application/json',
            'x-nosto-integration': 'Search Templates',
            'Accept': 'application/json'
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products using GraphQL API (single query with full variant data).

        Args:
            gender: 'men' or 'women'
            limit: Optional cap on total products returned

        Returns:
            List of normalised product dicts (each includes a 'variants' key)
        """
        category_id = self.CATEGORY_IDS.get(gender.lower())
        if not category_id:
            logger.error(f"Invalid gender: {gender}")
            return []

        products = []
        page_size = 24
        from_index = 0

        logger.info(f"Starting ShopWSS discovery for {gender} (category {category_id})")

        while True:
            try:
                payload = {
                    "query": DISCOVERY_QUERY,
                    "variables": {
                        "accountId": self.ACCOUNT_ID,
                        "products": {
                            "categoryId": category_id,
                            "size": page_size,
                            "from": from_index
                        }
                    }
                }

                logger.info(f"Fetching ShopWSS page: from={from_index}, size={page_size}")
                response = self.session.post(
                    self.GRAPHQL_URL,
                    json=payload,
                    headers=self.graphql_headers,
                    timeout=30
                )
                response.raise_for_status()

                data = response.json()
                search_data = data.get('data', {}).get('search', {}).get('products', {})
                hits = search_data.get('hits', [])
                total = search_data.get('total', 0)

                if not hits:
                    logger.info("No more products found")
                    break

                for hit in hits:
                    product_data = self._parse_hit(hit, gender)
                    if product_data:
                        products.append(product_data)

                logger.info(f"Fetched {len(hits)} products (total so far: {len(products)}/{total})")

                if limit and len(products) >= limit:
                    products = products[:limit]
                    logger.info(f"Reached limit of {limit} products")
                    break

                if from_index + page_size >= total:
                    logger.info(f"Reached end of results (total: {total})")
                    break

                from_index += page_size
                self.rate_limit(0.5)

            except Exception as e:
                logger.error(f"Error fetching ShopWSS products at index {from_index}: {e}")
                break

        logger.info(f"ShopWSS discovery complete: {len(products)} products found")
        return products

    def extract_product_details(self, sku: str) -> Optional[Dict]:
        """
        Refresh a single product by SKU using a GraphQL keyword search.
        The SKU is extracted from the product URL slug
        (e.g. 'vn000d3hbka' from '/products/vn000d3hbka').

        Args:
            sku: Product SKU / URL slug

        Returns:
            Normalised product dict or None
        """
        try:
            self.rate_limit(0.3)

            payload = {
                "query": REFRESH_QUERY,
                "variables": {
                    "accountId": self.ACCOUNT_ID,
                    "query": sku,
                    "products": {}
                }
            }

            logger.debug(f"Refreshing ShopWSS product: {sku}")
            response = self.session.post(
                self.GRAPHQL_URL,
                json=payload,
                headers=self.graphql_headers,
                timeout=30
            )

            if response.status_code == 429:
                logger.warning(f"Rate limited for SKU {sku}, skipping")
                return None

            response.raise_for_status()

            if not response.text or response.text.strip() == '':
                logger.warning(f"Empty response for SKU {sku}")
                return None

            data = response.json()
            hits = (
                data.get('data', {})
                    .get('search', {})
                    .get('products', {})
                    .get('hits', [])
            )

            if not hits:
                logger.warning(f"No results found for SKU {sku}")
                return None

            # Pick the closest match (first hit)
            hit = hits[0]
            return self._parse_hit(hit, gender=None)

        except Exception as e:
            logger.error(f"Error refreshing ShopWSS product {sku}: {e}")
            return None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _parse_hit(self, hit: Dict, gender: Optional[str]) -> Optional[Dict]:
        """Parse a GraphQL hit into a normalised product dict."""
        try:
            product_id = hit.get('productId')
            if not product_id:
                return None

            price = self._parse_price(hit.get('price'))

            # Availability — keep raw text for display, derive bool separately
            availability_text = hit.get('availability') or 'Unknown'
            available = hit.get('available')
            if available is None:
                # Fall back to text heuristic if 'available' field absent
                av_lower = availability_text.lower()
                available = 'instock' in av_lower or 'in stock' in av_lower

            variants = self._parse_skus(hit.get('skus') or [])

            result = {
                'id': str(product_id),
                'sku': str(product_id),
                'name': hit.get('name'),
                'title': hit.get('name'),
                'brand': hit.get('brand'),
                'url': hit.get('url'),
                'imageUrl': hit.get('imageUrl'),
                'image': hit.get('imageUrl'),
                'price': price,
                'currency': hit.get('priceCurrencyCode', 'USD'),
                'availability': availability_text,
                'available': available,
                'inventoryLevel': hit.get('inventoryLevel'),
                'variants': variants,
            }

            if gender:
                result['gender'] = gender

            return result

        except Exception as e:
            logger.error(f"Error parsing ShopWSS hit: {e}")
            return None

    def _parse_skus(self, skus: List[Dict]) -> List[Dict]:
        """Parse SKU list into variant dicts."""
        variants = []
        for sku in skus:
            custom_fields = {cf['key']: cf['value'] for cf in (sku.get('customFields') or [])}
            availability_text = sku.get('availability') or 'Unknown'
            av_lower = availability_text.lower()
            in_stock = 'instock' in av_lower or 'in stock' in av_lower

            variants.append({
                'sku': sku.get('id'),
                'name': sku.get('name'),
                'size': custom_fields.get('size'),
                'color': custom_fields.get('color'),
                'price': self._parse_price(sku.get('price')),
                'inventoryLevel': sku.get('inventoryLevel'),
                'availability': availability_text,
                'available': in_stock,
            })
        return variants

    def _parse_price(self, value) -> Optional[float]:
        """Coerce price to float."""
        if value is None:
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            try:
                return float(value.replace('$', '').replace(',', '').strip())
            except ValueError:
                return None
        return None

"""
ASOS Scraper
Handles product discovery and extraction from asos.com using REST APIs.
"""
import logging
from typing import List, Dict, Optional
from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class AsosScraper(BaseScraper):
    """Scraper for asos.com using their public REST APIs"""
    
    CATEGORY_IDS = {
        'men': '4209',
        'women': '4172'
    }
    
    SEARCH_API_URL = "https://www.asos.com/api/product/search/v2/categories/{category_id}"
    DETAIL_API_URL = "https://www.asos.com/api/product/catalogue/v4/summaries"
    VARIANT_API_URL = "https://www.asos.com/api/product/catalogue/v4/variants"
    
    def __init__(self, website_id: int, base_url: str = "https://www.asos.com"):
        super().__init__(website_id, base_url)
        
        # ASOS-specific headers - use browser-like headers to avoid 403
        self.session.headers.update({
            'Accept': 'application/json',
            'Accept-Language': 'en-US,en;q=0.9',
            'Referer': 'https://www.asos.com/men/',
            'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        })
    
    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products from ASOS search API.
        
        Args:
            gender: 'men' or 'women'
            limit: Optional limit on products to fetch
            
        Returns:
            List of product dictionaries
        """
        category_id = self.CATEGORY_IDS.get(gender.lower())
        if not category_id:
            logger.error(f"Invalid gender: {gender}")
            return []
        
        products = []
        offset = 0
        page_size = 72  # ASOS default page size
        
        logger.info(f"Starting ASOS discovery for {gender} (category {category_id})")
        
        while True:
            try:
                # Fetch page
                url = self.SEARCH_API_URL.format(category_id=category_id)
                params = {
                    'offset': offset,
                    'limit': page_size,
                    'store': 'US',
                    'country': 'US',
                    'currency': 'USD',
                    'lang': 'en-US'
                }
                
                # Rate limit before request to avoid overwhelming ASOS
                if offset > 0:
                    self.rate_limit(1.0)
                
                logger.info(f"Fetching ASOS page: offset={offset}, limit={page_size}")
                response = self.session.get(url, params=params, timeout=60)
                response.raise_for_status()
                
                data = response.json()
                
                # Extract products from response
                page_products = data.get('products', [])
                if not page_products:
                    logger.info("No more products found")
                    break
                
                # Process products
                for product in page_products:
                    product_data = self._parse_listing_product(product, gender)
                    if product_data:
                        products.append(product_data)
                
                logger.info(f"Fetched {len(page_products)} products (total: {len(products)})")
                
                # Check if we've reached the limit
                if limit and len(products) >= limit:
                    products = products[:limit]
                    logger.info(f"Reached limit of {limit} products")
                    break
                
                # Check if there are more pages
                total_items = data.get('itemCount', 0)
                if offset + page_size >= total_items:
                    logger.info(f"Reached end of results (total: {total_items})")
                    break
                
                # Move to next page
                offset += page_size
                
            except Exception as e:
                logger.error(f"Error fetching ASOS products at offset {offset}: {e}")
                break
        
        logger.info(f"ASOS discovery complete: {len(products)} products found")
        return products
    
    def extract_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Extract detailed product information including variants with price and availability.

        Two-step process:
        1. Fetch product summary (variant stubs: id, size, color)
        2. Enrich each variant with price + availability via fetch_variant_details()

        Args:
            product_id: ASOS product ID

        Returns:
            Dictionary with detailed product info including enriched variants
        """
        try:
            params = {
                'store': 'US',
                'productIds': product_id,
                'lang': 'en-US',
                'expand': 'variants',
                'country': 'US'
            }

            self.rate_limit(0.5)

            logger.debug(f"Fetching ASOS product details: {product_id}")
            response = self.session.get(self.DETAIL_API_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()

            if not (isinstance(data, list) and len(data) > 0):
                logger.warning(f"No details found for product {product_id}")
                return None

            parsed = self._parse_detail_product(data[0])
            if not parsed:
                return None

            variants = parsed.get('variants', [])

            # Enrich variant stubs with price + availability
            if variants:
                variant_ids = [v['id'] for v in variants if v.get('id')]
                details_map = self.fetch_variant_details(variant_ids)

                for variant in variants:
                    enriched = details_map.get(variant['id'], {})
                    variant['price'] = enriched.get('price')
                    variant['available'] = enriched.get('available')
                    variant['availability'] = enriched.get('availability')

            parsed['variants'] = variants
            return parsed

        except Exception as e:
            logger.error(f"Error fetching ASOS product details {product_id}: {e}")
            return None
    
    def _parse_listing_product(self, product: Dict, gender: str) -> Optional[Dict]:
        """Parse product from search listing"""
        try:
            product_id = product.get('id')
            if not product_id:
                return None
            
            # Extract price info
            price_data = product.get('price', {})
            current_price = None

            if isinstance(price_data, dict):
                current = price_data.get('current', {})
                if isinstance(current, dict):
                    current_price = current.get('value')
            
            return {
                'id': str(product_id),
                'sku': str(product_id),
                'name': product.get('name'),
                'title': product.get('name'),
                'brand': product.get('brandName'),
                'color': product.get('colour'),
                'url': f"https://www.asos.com/us/{product.get('url', '')}",
                'imageUrl': f"https://{product.get('imageUrl', '').lstrip('//')}" if product.get('imageUrl') else None,
                'image': f"https://{product.get('imageUrl', '').lstrip('//')}" if product.get('imageUrl') else None,
                'price': current_price,
                'gender': gender,
                # ASOS search API only surfaces actively listed products — assume in stock
                # at discovery time; scrape tasks will refine per-variant availability later
                'available': True,
                'availability': 'InStock',
            }
            
        except Exception as e:
            logger.error(f"Error parsing ASOS listing product: {e}")
            return None
    
    def _parse_detail_product(self, product: Dict) -> Optional[Dict]:
        """Parse detailed product information — returns variant stubs (id + size + color).
        Call fetch_variant_details() separately to enrich with price and availability."""
        try:
            variants = product.get('variants', [])
            variant_list = []

            for variant in variants:
                variant_id = variant.get('id')
                if not variant_id:
                    continue

                color = variant.get('colour') or variant.get('color')
                size = variant.get('brandSize') or variant.get('size')

                variant_list.append({
                    'id': str(variant_id),
                    'sku': str(variant_id),
                    'size': size,
                    'color': color,
                    'price': None,
                    'available': None,
                    'availability': None,
                    'inventoryLevel': None
                })

            return {'variants': variant_list}

        except Exception as e:
            logger.error(f"Error parsing ASOS detail product: {e}")
            return None

    def fetch_variant_details(self, variant_ids: List[str]) -> Dict[str, Dict]:
        """Fetch price and availability for a list of variant IDs.

        Returns a dict keyed by variant ID with 'price' and 'available' values.
        """
        if not variant_ids:
            return {}

        try:
            params = {
                'store': 'US',
                'variantIds': ','.join(str(v) for v in variant_ids),
                'lang': 'en-US',
                'expand': 'variants',
                'country': 'US'
            }

            self.rate_limit(0.5)
            logger.debug(f"Fetching ASOS variant details for {len(variant_ids)} variants")
            response = self.session.get(self.VARIANT_API_URL, params=params, timeout=60)
            response.raise_for_status()

            data = response.json()
            result = {}

            items = data if isinstance(data, list) else data.get('variants', [])
            for item in items:
                vid = str(item.get('variantId') or item.get('id', ''))
                if not vid:
                    continue

                price = None
                price_data = item.get('price', {})
                if isinstance(price_data, dict):
                    current = price_data.get('current', {})
                    if isinstance(current, dict):
                        price = current.get('value')

                is_in_stock = item.get('isInStock', False)

                result[vid] = {
                    'price': price,
                    'available': is_in_stock,
                    'availability': 'InStock' if is_in_stock else 'OutOfStock'
                }

            return result

        except Exception as e:
            logger.error(f"Error fetching ASOS variant details: {e}")
            return {}

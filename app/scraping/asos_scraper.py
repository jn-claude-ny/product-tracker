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
        Extract detailed product information including variants.
        
        Args:
            product_id: ASOS product ID
            
        Returns:
            Dictionary with detailed product info
        """
        try:
            params = {
                'store': 'US',
                'productIds': product_id,
                'lang': 'en-US',
                'expand': 'variants',
                'country': 'US'
            }
            
            # Rate limit to avoid overwhelming API
            self.rate_limit(0.5)
            
            logger.debug(f"Fetching ASOS product details: {product_id}")
            response = self.session.get(self.DETAIL_API_URL, params=params, timeout=60)
            response.raise_for_status()
            
            data = response.json()
            
            # ASOS returns an array, get first item
            if isinstance(data, list) and len(data) > 0:
                product_data = data[0]
                return self._parse_detail_product(product_data)
            
            logger.warning(f"No details found for product {product_id}")
            return None
            
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
            sale_price = None
            
            if isinstance(price_data, dict):
                current = price_data.get('current', {})
                previous = price_data.get('previous', {})
                
                if isinstance(current, dict):
                    current_price = current.get('value')
                
                if isinstance(previous, dict):
                    prev_value = previous.get('value')
                    if prev_value and current_price and prev_value > current_price:
                        sale_price = current_price
                        current_price = prev_value
            
            is_in_stock = product.get('isInStock', True)
            return {
                'id': str(product_id),
                'sku': str(product_id),
                'name': product.get('name'),
                'title': product.get('name'),
                'brand': product.get('brandName'),
                'url': f"https://www.asos.com/us/{product.get('url', '')}",
                'imageUrl': f"https://{product.get('imageUrl', '').lstrip('//')}" if product.get('imageUrl') else None,
                'image': f"https://{product.get('imageUrl', '').lstrip('//')}" if product.get('imageUrl') else None,
                'price': current_price,
                'salePrice': sale_price,
                'available': is_in_stock,
                'availability': 'InStock' if is_in_stock else 'OutOfStock',
                'isOnSale': sale_price is not None,
                'isNew': product.get('isNoSize', False),
                'gender': gender
            }
            
        except Exception as e:
            logger.error(f"Error parsing ASOS listing product: {e}")
            return None
    
    def _parse_detail_product(self, product: Dict) -> Optional[Dict]:
        """Parse detailed product information"""
        try:
            variants = product.get('variants', [])
            
            # Extract size range
            sizes = []
            colors = set()
            variant_list = []
            
            for variant in variants:
                size = variant.get('size')
                color = variant.get('colour') or variant.get('color')
                is_in_stock = variant.get('isInStock', False)
                
                if size:
                    sizes.append(size)
                if color:
                    colors.add(color)
                
                variant_price = None
                price_data = variant.get('price', {})
                if isinstance(price_data, dict):
                    current = price_data.get('current', {})
                    if isinstance(current, dict):
                        variant_price = current.get('value')

                variant_list.append({
                    'sku': str(variant.get('variantId', '')),
                    'size': size,
                    'color': color,
                    'price': variant_price,
                    'available': is_in_stock,
                    'availability': 'InStock' if is_in_stock else 'OutOfStock',
                    'inventoryLevel': None
                })
            
            # Determine size range
            size_range = None
            if sizes:
                try:
                    numeric_sizes = [float(s) for s in sizes if s and s.replace('.', '').isdigit()]
                    if numeric_sizes:
                        size_range = f"{min(numeric_sizes)}-{max(numeric_sizes)}"
                except:
                    pass
            
            return {
                'variants': variant_list,
                'size_range': size_range,
                'color': ', '.join(sorted(colors)) if colors else None,
                'description': product.get('description'),
                'productCode': product.get('productCode')
            }
            
        except Exception as e:
            logger.error(f"Error parsing ASOS detail product: {e}")
            return None

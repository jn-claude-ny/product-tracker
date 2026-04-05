"""
ShopWSS Scraper
Handles product discovery and extraction from shopwss.com using GraphQL and Bazaarvoice APIs.
"""
import logging
from typing import List, Dict, Optional
from app.scraping.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class ShopWssScraper(BaseScraper):
    """Scraper for shopwss.com using GraphQL (Nosto) and Bazaarvoice APIs"""
    
    CATEGORY_IDS = {
        'men': '153376063543',
        'women': '153381568567'
    }
    
    GRAPHQL_URL = "https://search.nosto.com/v1/graphql"
    BAZAARVOICE_URL = "https://apps.bazaarvoice.com/bfd/v1/clients/wss/api-products/cv2/resources/data/products.json"
    ACCOUNT_ID = "shopify-6934429751"
    
    def __init__(self, website_id: int, base_url: str = "https://www.shopwss.com"):
        super().__init__(website_id, base_url)
        
        # GraphQL-specific headers
        self.graphql_headers = {
            'Content-Type': 'application/json',
            'x-nosto-integration': 'Search Templates',
            'Accept': 'application/json'
        }
        
        # Bazaarvoice-specific headers
        self.bv_headers = {
            'Accept': 'application/json',
            'Accept-Encoding': 'gzip, deflate',  # Ensure gzip decompression works
            'bv-bfd-token': '18656,main_site,en_US',
            'Origin': 'https://www.shopwss.com',
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products using GraphQL API.
        
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
        page_size = 24  # ShopWSS default
        from_index = 0
        
        logger.info(f"Starting ShopWSS discovery for {gender} (category {category_id})")
        
        while True:
            try:
                # Build GraphQL query
                query = """
                query ($accountId: String, $products: InputSearchProducts) {
                    search(accountId: $accountId, products: $products) {
                        products {
                            hits {
                                productId
                                name
                                url
                                imageUrl
                                brand
                                price
                                priceText
                                availability
                            }
                            total
                            size
                            from
                        }
                    }
                }
                """
                
                variables = {
                    "accountId": self.ACCOUNT_ID,
                    "products": {
                        "categoryId": category_id,
                        "size": page_size,
                        "from": from_index
                    }
                }
                
                payload = {
                    "query": query,
                    "variables": variables
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
                
                # Extract products from GraphQL response
                search_data = data.get('data', {}).get('search', {}).get('products', {})
                hits = search_data.get('hits', [])
                total = search_data.get('total', 0)
                
                if not hits:
                    logger.info("No more products found")
                    break
                
                # Process products
                for hit in hits:
                    product_data = self._parse_listing_product(hit, gender)
                    if product_data:
                        products.append(product_data)
                
                logger.info(f"Fetched {len(hits)} products (total: {len(products)}/{total})")
                
                # Check if we've reached the limit
                if limit and len(products) >= limit:
                    products = products[:limit]
                    logger.info(f"Reached limit of {limit} products")
                    break
                
                # Check if there are more pages
                if from_index + page_size >= total:
                    logger.info(f"Reached end of results (total: {total})")
                    break
                
                # Move to next page
                from_index += page_size
                self.rate_limit(0.5)  # Rate limiting
                
            except Exception as e:
                logger.error(f"Error fetching ShopWSS products at index {from_index}: {e}")
                break
        
        logger.info(f"ShopWSS discovery complete: {len(products)} products found")
        return products
    
    def extract_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Extract detailed product information from Bazaarvoice API.
        
        Args:
            product_id: ShopWSS product ID
            
        Returns:
            Dictionary with detailed product info
        """
        try:
            # Rate limit to avoid overwhelming the API
            self.rate_limit(0.3)
            
            params = {
                'locale': 'en_US',
                'allowMissing': 'true',
                'apiVersion': '5.4',
                'filter': f'id:{product_id}'
            }
            
            logger.debug(f"Fetching ShopWSS product details: {product_id}")
            response = self.session.get(
                self.BAZAARVOICE_URL,
                params=params,
                headers=self.bv_headers,
                timeout=30
            )
            
            # Check status before trying to parse
            if response.status_code == 429:
                logger.warning(f"Rate limited for product {product_id}, skipping")
                return None
            
            response.raise_for_status()
            
            # Check if response has content
            if not response.text or response.text.strip() == '':
                logger.warning(f"Empty response for product {product_id}")
                return None
            
            try:
                # response.json() should automatically handle gzip decompression
                data = response.json()
            except ValueError as json_err:
                # Log the actual content-encoding to debug compression issues
                encoding = response.headers.get('Content-Encoding', 'none')
                logger.error(f"JSON decode error for product {product_id} (encoding: {encoding}): {json_err}")
                return None
            
            # Parse Bazaarvoice response - check for 'response' wrapper
            if 'response' in data:
                response_data = data.get('response', {})
                if response_data is None:
                    logger.warning(f"Null response data for product {product_id}")
                    return None
                results = response_data.get('Results', [])
            else:
                results = data.get('Results', [])
            
            if results and len(results) > 0:
                product_data = results[0]
                return self._parse_detail_product(product_data)
            
            logger.warning(f"No details found for product {product_id}")
            return None
            
        except requests.exceptions.RequestException as req_err:
            logger.error(f"Request error for product {product_id}: {req_err}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error fetching product {product_id}: {e}")
            return None
    
    def _parse_listing_product(self, hit: Dict, gender: str) -> Optional[Dict]:
        """Parse product from GraphQL listing"""
        try:
            product_id = hit.get('productId')
            if not product_id:
                return None
            
            # Parse price
            price = hit.get('price')
            if isinstance(price, str):
                price = float(price.replace('$', '').replace(',', ''))
            
            # Normalize availability
            availability = hit.get('availability', '').lower()
            is_in_stock = 'instock' in availability or 'in stock' in availability
            
            return {
                'id': str(product_id),
                'sku': str(product_id),
                'name': hit.get('name'),
                'brand': hit.get('brand'),
                'url': hit.get('url'),
                'imageUrl': hit.get('imageUrl'),
                'price': price,
                'priceText': hit.get('priceText'),
                'availability': 'InStock' if is_in_stock else 'OutOfStock',
                'isInStock': is_in_stock,
                'gender': gender
            }
            
        except Exception as e:
            logger.error(f"Error parsing ShopWSS listing product: {e}")
            return None
    
    def _parse_detail_product(self, product: Dict) -> Optional[Dict]:
        """Parse detailed product information from Bazaarvoice"""
        try:
            # Extract attributes
            attributes = product.get('Attributes', {})
            
            # Extract variants/sizes if available
            variants = []
            sizes = set()
            colors = set()
            
            # Bazaarvoice may have size/color in different structures
            # Check for common fields
            size_attr = attributes.get('Size') or attributes.get('size')
            color_attr = attributes.get('Color') or attributes.get('color')
            
            if size_attr:
                if isinstance(size_attr, list):
                    sizes.update(size_attr)
                else:
                    sizes.add(str(size_attr))
            
            if color_attr:
                if isinstance(color_attr, list):
                    colors.update(color_attr)
                else:
                    colors.add(str(color_attr))
            
            # Try to extract variants from product data
            variant_data = product.get('Variants', [])
            for variant in variant_data:
                variant_info = {
                    'sku': variant.get('Id') or variant.get('SKU'),
                    'size': variant.get('Size'),
                    'color': variant.get('Color'),
                    'price': variant.get('Price'),
                    'availability': 'InStock' if variant.get('InStock') else 'OutOfStock'
                }
                variants.append(variant_info)
                
                if variant.get('Size'):
                    sizes.add(str(variant.get('Size')))
                if variant.get('Color'):
                    colors.add(str(variant.get('Color')))
            
            # Determine size range
            size_range = None
            if sizes:
                try:
                    numeric_sizes = [float(s) for s in sizes if s and str(s).replace('.', '').isdigit()]
                    if numeric_sizes:
                        size_range = f"{min(numeric_sizes)}-{max(numeric_sizes)}"
                except:
                    pass
            
            return {
                'variants': variants,
                'size_range': size_range,
                'color': ', '.join(sorted(colors)) if colors else None,
                'description': product.get('Description') or product.get('BrandDescription'),
                'productCode': product.get('Id')
            }
            
        except Exception as e:
            logger.error(f"Error parsing ShopWSS detail product: {e}")
            return None

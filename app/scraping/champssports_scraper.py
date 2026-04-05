"""
ChampsSports Scraper using Zendriver
Handles product discovery and extraction from champssports.com using API interception.
"""
import asyncio
import json
import base64
import logging
import os
from typing import List, Dict, Optional
from datetime import datetime
from app.scraping.base_scraper import BaseScraper
from zendriver.cdp.network import get_response_body

logger = logging.getLogger(__name__)


class ChampsSportsScraper(BaseScraper):
    """Scraper for champssports.com using zendriver and API interception"""
    
    def __init__(self, website_id: int, base_url: str = "https://www.champssports.com"):
        super().__init__(website_id, base_url)
        self.proxies = {
            "server": os.getenv('CHAMPS_PROXY_SERVER', ''),
            "username": os.getenv('CHAMPS_PROXY_USERNAME', ''),
            "password": os.getenv('CHAMPS_PROXY_PASSWORD', ''),
        }
        self.user_data_dir = os.path.join(os.path.dirname(__file__), 'champ_data')
    
    async def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products from ChampsSports using API interception.
        
        Args:
            gender: 'men' or 'women'
            limit: Optional limit on products to fetch
            
        Returns:
            List of product dictionaries with basic info
        """
        logger.info(f"Starting ChampsSports discovery for {gender}")
        
        try:
            import zendriver as zd
            
            browser = await zd.start(
                headless=True, 
                proxy=self.proxies, 
                user_data_dir=self.user_data_dir
            )
            tab = await browser.get("about:blank")
            
            try:
                # Establish session
                logger.info("Establishing session...")
                await tab.get("https://www.champssports.com")
                await asyncio.sleep(3)
                
                # Load the category page
                category_path = "mens" if gender.lower() == "men" else "womens"
                logger.info(f"Loading {gender} category page...")
                await tab.get(f"https://www.champssports.com/category/{category_path}/shoes.html")
                await asyncio.sleep(5)
                
                all_products = []
                page_num = 0
                max_pages = 10  # Safety limit
                
                while page_num < max_pages:
                    logger.info(f"Processing page {page_num + 1}")
                    
                    # Handle pagination
                    if page_num == 0:
                        # For first page, click page 1 to trigger API
                        page1_button = await tab.find("a[aria-label='Go to next page']")
                        if not page1_button:
                            page1_button = await tab.find("a:has-text('1')")
                        
                        if page1_button:
                            response = await self._trigger_api_call(tab, page1_button)
                        else:
                            logger.warning("No page 1 button found, trying to refresh...")
                            await tab.reload()
                            await asyncio.sleep(5)
                            continue
                    else:
                        # For subsequent pages, click Next
                        next_link = await tab.find("a[aria-label='Go to next page']")
                        if not next_link:
                            logger.info("No Next link found - finished pagination")
                            break
                        
                        response = await self._trigger_api_call(tab, next_link)
                    
                    if not response:
                        logger.warning(f"No response for page {page_num + 1}")
                        break
                    
                    # Extract products from API response
                    products = await self._extract_products_from_response(response)
                    if not products:
                        logger.warning(f"No products found on page {page_num + 1}")
                        break
                    
                    all_products.extend(products)
                    logger.info(f"Found {len(products)} products on page {page_num + 1}")
                    
                    # Check limit
                    if limit and len(all_products) >= limit:
                        all_products = all_products[:limit]
                        break
                    
                    page_num += 1
                    await asyncio.sleep(2)  # Rate limiting
                
                logger.info(f"Total products discovered: {len(all_products)}")
                return self._normalize_discovered_products(all_products, gender)
                
            finally:
                await browser.stop()
                
        except Exception as e:
            logger.error(f"Error discovering ChampsSports products: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def _trigger_api_call(self, tab, button):
        """Trigger API call by clicking button and waiting for response"""
        try:
            async with tab.expect_response(".*zgw/search-core/products/v3/search.*") as response_expectation:
                await button.click()
                await asyncio.sleep(5)
                response = await response_expectation.value
            return response
        except Exception as e:
            logger.error(f"Error triggering API call: {e}")
            return None
    
    async def _extract_products_from_response(self, response) -> List[Dict]:
        """Extract products from API response"""
        try:
            body, is_base64 = await response.tab.send(get_response_body(request_id=response.request_id))
            
            if is_base64:
                body = base64.b64decode(body).decode('utf-8')
            
            data = json.loads(body)
            
            if data.get('products'):
                return data['products']
            else:
                logger.warning(f"No products in response. Keys: {list(data.keys())}")
                return []
                
        except json.JSONDecodeError as e:
            logger.error(f"JSON decode error: {e}")
            return []
        except Exception as e:
            logger.error(f"Error extracting products from response: {e}")
            return []
    
    def _normalize_discovered_products(self, products: List[Dict], gender: str) -> List[Dict]:
        """Normalize discovered products to standard format"""
        normalized = []
        
        for product in products:
            try:
                # Extract basic info from API response
                normalized_product = {
                    'sku': product.get('sku'),
                    'title': product.get('name') or product.get('title'),
                    'brand': product.get('brand') or product.get('brandName'),
                    'url': self._build_product_url(product),
                    'image': product.get('image') or product.get('imageUrl'),
                    'gender': gender,
                    'category': product.get('category'),
                    'color': product.get('color'),
                    'price_current': self._extract_price(product.get('price')),
                    'currency': product.get('currency', 'USD'),
                    'is_on_sale': product.get('is_on_sale', False) or product.get('isOnSale', False),
                    'is_new': product.get('is_new', False) or product.get('isNew', False),
                    'categories': product.get('categories', [])
                }
                
                # Only include if we have essential data
                if normalized_product['sku'] and normalized_product['title']:
                    normalized.append(normalized_product)
                    
            except Exception as e:
                logger.warning(f"Error normalizing product: {e}")
                continue
        
        return normalized
    
    def _build_product_url(self, product: Dict) -> str:
        """Build product URL from API data"""
        try:
            # Try to get URL parts from product data
            if 'url' in product:
                return product['url']
            
            # Build URL from name and SKU
            name = product.get('name', '').lower()
            sku = product.get('sku', '')
            
            if name and sku:
                # Normalize name for URL
                name_slug = name.replace(' ', '-').replace("'", '').replace('"', '')
                return f"https://www.champssports.com/product/{name_slug}/{sku}.html"
            
            return f"https://www.champssports.com/product/{sku}.html" if sku else ""
            
        except Exception as e:
            logger.warning(f"Error building product URL: {e}")
            return ""
    
    async def extract_product_details(self, product_url: str) -> Optional[Dict]:
        """
        Extract detailed product information using API interception.
        
        Args:
            product_url: Full product URL
            
        Returns:
            Dictionary with detailed product information
        """
        try:
            import zendriver as zd
            
            browser = await zd.start(
                headless=True, 
                proxy=self.proxies, 
                user_data_dir=self.user_data_dir
            )
            tab = await browser.get("about:blank")
            
            try:
                # Intercept product details API call
                async with tab.expect_response(".*zgw/product-core/v1/pdp/sku.*") as response_expectation:
                    await tab.get(product_url)
                    await asyncio.sleep(0.5)
                    response = await response_expectation.value
                
                # Extract and parse response
                body, is_base64 = await tab.send(get_response_body(request_id=response.request_id))
                
                if is_base64:
                    body = base64.b64decode(body).decode('utf-8')
                
                data = json.loads(body)
                
                # Normalize the detailed product data
                return self._normalize_product_details(data, product_url)
                
            finally:
                await browser.stop()
                
        except Exception as e:
            logger.error(f"Error extracting ChampsSports product details: {e}")
            return None
    
    def _normalize_product_details(self, data: Dict, product_url: str) -> Dict:
        """Normalize detailed product data from API"""
        try:
            # Extract the main product data
            product = data.get('product', data)
            
            normalized = {
                'url': product_url,
                'sku': product.get('sku') or product.get('productId'),
                'title': product.get('name') or product.get('title'),
                'brand': product.get('brand') or product.get('brandName'),
                'description': product.get('description'),
                'image': product.get('image') or product.get('imageUrl'),
                'images': product.get('images', []),
                'gender': product.get('gender'),
                'category': product.get('category'),
                'color': product.get('color'),
                'price_current': self._extract_price(product.get('price')),
                'price_previous': self._extract_price(product.get('originalPrice') or product.get('previousPrice')),
                'currency': product.get('currency', 'USD'),
                'is_on_sale': product.get('is_on_sale', False) or product.get('isOnSale', False),
                'is_new': product.get('is_new', False) or product.get('isNew', False),
                'categories': product.get('categories', []),
                'availability': self._normalize_availability(product),
                'sizes': self._extract_sizes(product),
                'material': product.get('material'),
                'style_code': product.get('styleCode') or product.get('style'),
                'model_number': product.get('modelNumber'),
                'release_date': product.get('releaseDate'),
                'detail_last_fetched': datetime.utcnow()
            }
            
            return normalized
            
        except Exception as e:
            logger.error(f"Error normalizing product details: {e}")
            return {'url': product_url, 'detail_last_fetched': datetime.utcnow()}
    
    def _extract_sizes(self, product: Dict) -> List[str]:
        """Extract available sizes from product data"""
        try:
            sizes = []
            
            # Try different size formats
            if 'sizes' in product:
                sizes_data = product['sizes']
                if isinstance(sizes_data, list):
                    for size_info in sizes_data:
                        if isinstance(size_info, dict):
                            size = size_info.get('size') or size_info.get('name')
                            if size and size_info.get('available', True):
                                sizes.append(size)
                        elif isinstance(size_info, str):
                            sizes.append(size_info)
            
            # Try variants
            if 'variants' in product and not sizes:
                for variant in product['variants']:
                    size = variant.get('size')
                    if size and variant.get('available', True):
                        sizes.append(size)
            
            return list(set(sizes))  # Remove duplicates
            
        except Exception as e:
            logger.warning(f"Error extracting sizes: {e}")
            return []
    
    def extract_product_details_sync(self, product_url: str) -> Optional[Dict]:
        """
        Synchronous wrapper for extract_product_details.
        This is required by the base scraper interface.
        """
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.extract_product_details(product_url))
            return result
        except Exception as e:
            logger.error(f"Error in sync wrapper: {e}")
            return None
        finally:
            if loop:
                loop.close()
    
    def discover_products_sync(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Synchronous wrapper for discover_products.
        This is required by the base scraper interface.
        """
        loop = None
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self.discover_products(gender, limit))
            return result
        except Exception as e:
            logger.error(f"Error in sync wrapper: {e}")
            return []
        finally:
            if loop:
                loop.close()

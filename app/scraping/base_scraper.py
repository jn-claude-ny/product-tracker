"""
Base Scraper Class
Provides common functionality for all site-specific scrapers.
"""
import time
import logging
from typing import List, Dict, Optional
from abc import ABC, abstractmethod
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class BaseScraper(ABC):
    """Abstract base class for site-specific scrapers"""
    
    def __init__(self, website_id: int, base_url: str):
        self.website_id = website_id
        self.base_url = base_url
        self.session = self._create_session()
        
    def _create_session(self) -> requests.Session:
        """Create requests session with retry logic"""
        session = requests.Session()
        session.verify = False  # Disable SSL verification
        
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "OPTIONS"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        # Default headers
        session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        })
        
        return session
    
    @abstractmethod
    def discover_products(self, gender: str, limit: Optional[int] = None) -> List[Dict]:
        """
        Discover products for a given gender category.
        
        Args:
            gender: 'men' or 'women'
            limit: Optional limit on number of products to discover
            
        Returns:
            List of product dictionaries with basic info
        """
        pass
    
    @abstractmethod
    def extract_product_details(self, product_id: str) -> Optional[Dict]:
        """
        Extract detailed information for a specific product.
        
        Args:
            product_id: Product identifier
            
        Returns:
            Dictionary with detailed product information
        """
        pass
    
    def normalize_product_data(self, raw_data: Dict, gender: str) -> Dict:
        """
        Normalize raw product data to standard format.
        
        Args:
            raw_data: Raw product data from scraper
            gender: Gender category
            
        Returns:
            Normalized product dictionary
        """
        return {
            'sku': raw_data.get('sku') or raw_data.get('id') or raw_data.get('productId'),
            'title': raw_data.get('title') or raw_data.get('name'),
            'brand': raw_data.get('brand') or raw_data.get('brandName'),
            'url': raw_data.get('url'),
            'image': raw_data.get('image') or raw_data.get('imageUrl'),
            'gender': gender,
            'category': raw_data.get('category'),
            'color': raw_data.get('color') or raw_data.get('colour'),
            'price_current': self._extract_price(raw_data.get('price')) or raw_data.get('price_current'),
            'currency': raw_data.get('currency', 'USD'),
            'is_on_sale': raw_data.get('is_on_sale', False) or raw_data.get('isOnSale', False),
            'is_new': raw_data.get('is_new', False) or raw_data.get('isNew', False),
            'categories': raw_data.get('categories', []),
            'availability': raw_data.get('availability'),
            'available': raw_data.get('available'),
            'inventoryLevel': raw_data.get('inventoryLevel'),
        }
    
    def _extract_price(self, price_data) -> Optional[float]:
        """Extract price from various formats"""
        if price_data is None:
            return None
        
        if isinstance(price_data, (int, float)):
            return float(price_data)
        
        if isinstance(price_data, dict):
            # Handle nested price objects (e.g., ASOS)
            if 'current' in price_data:
                return self._extract_price(price_data['current'])
            if 'value' in price_data:
                return float(price_data['value'])
        
        if isinstance(price_data, str):
            # Remove currency symbols and parse
            import re
            price_str = re.sub(r'[^\d.]', '', price_data)
            try:
                return float(price_str)
            except ValueError:
                return None
        
        return None
    
    def _normalize_availability(self, raw_data: Dict) -> str:
        """Normalize availability status"""
        availability = raw_data.get('availability', '').lower()
        is_in_stock = raw_data.get('isInStock') or raw_data.get('is_in_stock')
        
        if is_in_stock is not None:
            return 'InStock' if is_in_stock else 'OutOfStock'
        
        if 'instock' in availability or 'in stock' in availability:
            return 'InStock'
        elif 'outofstock' in availability or 'out of stock' in availability:
            return 'OutOfStock'
        elif 'low' in availability:
            return 'LowStock'
        
        return 'Unknown'
    
    def rate_limit(self, delay: float = 1.0):
        """Apply rate limiting between requests"""
        time.sleep(delay)
    
    def close(self):
        """Close session"""
        if self.session:
            self.session.close()

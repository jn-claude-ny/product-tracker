"""
Scraper Factory
Creates appropriate scraper instance based on website URL.
"""
import logging
from typing import Optional
from app.scraping.base_scraper import BaseScraper
from app.scraping.asos_scraper import AsosScraper
from app.scraping.shopwss_scraper import ShopWssScraper
from app.scraping.champssports_scraper import ChampsSportsScraper

logger = logging.getLogger(__name__)


class ScraperFactory:
    """Factory for creating site-specific scrapers"""
    
    @staticmethod
    def create_scraper(website_id: int, base_url: str) -> Optional[BaseScraper]:
        """
        Create appropriate scraper based on website URL.
        
        Args:
            website_id: Database ID of the website
            base_url: Base URL of the website
            
        Returns:
            Scraper instance or None if unsupported
        """
        base_url_lower = base_url.lower()
        
        if 'asos.com' in base_url_lower:
            logger.info(f"Creating ASOS scraper for website {website_id}")
            return AsosScraper(website_id, base_url)
        
        elif 'shopwss.com' in base_url_lower:
            logger.info(f"Creating ShopWSS scraper for website {website_id}")
            return ShopWssScraper(website_id, base_url)
        
        elif 'champssports.com' in base_url_lower:
            logger.info(f"Creating ChampsSports scraper for website {website_id}")
            return ChampsSportsScraper(website_id, base_url)
        
        else:
            logger.warning(f"No scraper available for {base_url}")
            return None
    
    @staticmethod
    def get_supported_sites() -> list:
        """Get list of supported site domains"""
        return [
            'asos.com',
            'shopwss.com',
            'champssports.com'
        ]
    
    @staticmethod
    def is_supported(base_url: str) -> bool:
        """Check if a website is supported"""
        base_url_lower = base_url.lower()
        return any(site in base_url_lower for site in ScraperFactory.get_supported_sites())

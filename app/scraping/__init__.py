"""
Scraping module for multi-site product extraction.
"""
from app.scraping.base_scraper import BaseScraper
from app.scraping.asos_scraper import AsosScraper
from app.scraping.shopwss_scraper import ShopWssScraper
from app.scraping.champssports_scraper import ChampsSportsScraper
from app.scraping.scraper_factory import ScraperFactory

__all__ = [
    'BaseScraper',
    'AsosScraper',
    'ShopWssScraper',
    'ChampsSportsScraper',
    'ScraperFactory'
]

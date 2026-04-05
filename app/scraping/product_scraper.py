from typing import Dict, Optional, Any
import hashlib
import logging
from app.scraping.http_scraper import HttpScraper
from app.scraping.playwright_scraper import PlaywrightScraper
from app.scraping.selector_engine import SelectorEngine
from app.models.website import Website

logger = logging.getLogger(__name__)


class ProductScraper:
    def __init__(self, website: Website):
        self.website = website
        self.selectors = {s.field_name: s for s in website.selectors.all()}

    def scrape(self, url: str) -> Optional[Dict[str, Any]]:
        try:
            html_content = self._fetch_html(url)
            if not html_content:
                return None

            data = self._extract_data(html_content, url)
            if not data:
                return None

            data['url'] = url
            data['hash'] = self._compute_hash(data)

            return data

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    def _fetch_html(self, url: str) -> Optional[str]:
        if self.website.use_playwright:
            scraper = PlaywrightScraper(self.website.id)
            return scraper.fetch(
                url,
                wait_selector=self.website.wait_selector,
                delay=float(self.website.scrape_delay_seconds),
                randomize_delay=self.website.randomize_delay
            )
        else:
            scraper = HttpScraper(proxy_group=self.website.proxy_group)
            return scraper.fetch(
                url,
                delay=float(self.website.scrape_delay_seconds),
                randomize_delay=self.website.randomize_delay
            )

    def _extract_data(self, html_content: str, url: str = '') -> Optional[Dict[str, Any]]:
        engine = SelectorEngine(html_content)
        data = {}

        for field_name, selector in self.selectors.items():
            try:
                value = engine.extract_field(
                    selector.selector_type,
                    selector.selector_value,
                    selector.post_process
                )
            except Exception as e:
                logger.warning(
                    f'Failed to extract {selector.name} for {url} '
                    f'using selector {selector.selector}: {e}'
                )
                value = None
            data[field_name] = value

        if not self._validate_data(data):
            return None

        return data

    def _validate_data(self, data: Dict[str, Any]) -> bool:
        if 'price' in data and data['price']:
            try:
                # Remove currency symbols and whitespace before validation
                price_str = str(data['price']).replace('$', '').replace('€', '').replace('£', '').replace(',', '').strip()
                float(price_str)
            except (ValueError, TypeError):
                logger.warning(f"Invalid price value: {data['price']}")
                return False

        if not data.get('title'):
            logger.warning("Missing title")
            return False

        return True

    def _compute_hash(self, data: Dict[str, Any]) -> str:
        hash_fields = ['title', 'brand', 'price', 'availability', 'sku']
        hash_string = ''.join([
            str(data.get(field, '')) for field in hash_fields
        ])
        return hashlib.sha256(hash_string.encode()).hexdigest()

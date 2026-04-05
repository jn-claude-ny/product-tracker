from playwright.sync_api import sync_playwright, Browser, BrowserContext
from typing import Optional, Dict
import logging
import time
import random

logger = logging.getLogger(__name__)


class PlaywrightBrowserPool:
    _instance = None
    _browser: Optional[Browser] = None
    _contexts: Dict[int, BrowserContext] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._browser is None:
            self._initialize_browser()

    def _initialize_browser(self):
        try:
            self.playwright = sync_playwright().start()
            self._browser = self.playwright.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-blink-features=AutomationControlled',
                ]
            )
            logger.info("Playwright browser initialized")
        except Exception as e:
            logger.error(f"Failed to initialize Playwright browser: {e}")
            raise

    def get_context(self, website_id: int) -> BrowserContext:
        if website_id not in self._contexts:
            self._contexts[website_id] = self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            logger.info(f"Created new browser context for website {website_id}")
        return self._contexts[website_id]

    def close_context(self, website_id: int):
        if website_id in self._contexts:
            self._contexts[website_id].close()
            del self._contexts[website_id]
            logger.info(f"Closed browser context for website {website_id}")

    def close(self):
        for context in self._contexts.values():
            context.close()
        self._contexts.clear()
        if self._browser:
            self._browser.close()
        if hasattr(self, 'playwright'):
            self.playwright.stop()
        logger.info("Playwright browser pool closed")


class PlaywrightScraper:
    def __init__(self, website_id: int):
        self.website_id = website_id
        self.pool = PlaywrightBrowserPool()
        self.context = self.pool.get_context(website_id)

    def fetch(self, url: str, wait_selector: Optional[str] = None,
              delay: float = 3.0, randomize_delay: bool = True) -> Optional[str]:
        if randomize_delay:
            actual_delay = delay * random.uniform(0.5, 1.5)
        else:
            actual_delay = delay

        time.sleep(actual_delay)

        page = None
        try:
            page = self.context.new_page()

            page.goto(url, wait_until='domcontentloaded', timeout=30000)

            if wait_selector:
                try:
                    page.wait_for_selector(wait_selector, timeout=10000)
                except Exception as e:
                    logger.warning(f"Wait selector '{wait_selector}' not found for {url}: {e}")
            else:
                page.wait_for_load_state('networkidle', timeout=10000)

            content = page.content()

            return content

        except Exception as e:
            logger.error(f"Error fetching {url} with Playwright: {e}")
            raise
        finally:
            if page:
                page.close()

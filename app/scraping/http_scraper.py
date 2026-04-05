import httpx
import random
import time
from typing import Optional
from app.config import Config
import logging

logger = logging.getLogger(__name__)


class HttpScraper:
    def __init__(self, proxy_group: Optional[str] = None):
        self.proxy_group = proxy_group
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        ]

    def get_proxy_config(self) -> Optional[dict]:
        if not Config.BRIGHTDATA_PROXY_HOST:
            return None

        proxy_url = f"http://{Config.BRIGHTDATA_PROXY_USERNAME}:{Config.BRIGHTDATA_PROXY_PASSWORD}@{Config.BRIGHTDATA_PROXY_HOST}:{Config.BRIGHTDATA_PROXY_PORT}"

        return {
            'http://': proxy_url,
            'https://': proxy_url
        }

    def get_random_user_agent(self) -> str:
        return random.choice(self.user_agents)

    def fetch(self, url: str, delay: float = 3.0, randomize_delay: bool = True) -> Optional[str]:
        if randomize_delay:
            actual_delay = delay * random.uniform(0.5, 1.5)
        else:
            actual_delay = delay

        time.sleep(actual_delay)

        headers = {
            'User-Agent': self.get_random_user_agent(),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate, br',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

        proxies = self.get_proxy_config()

        try:
            with httpx.Client(proxies=proxies, timeout=30.0, follow_redirects=True, verify=False) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
                return response.text
        except Exception as e:
            logger.error(f"Error fetching {url}: {e}")
            raise

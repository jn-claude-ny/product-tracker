import httpx
import gzip
import redis
import xml.etree.ElementTree as ET
from lxml import etree
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
import logging
import hashlib
from typing import List, Tuple, Optional
from app.config import Config

logger = logging.getLogger(__name__)


class SitemapParser:
    def __init__(self):
        self.redis_client = redis.from_url(Config.REDIS_URL)
        self.tracking_params = [
            'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
            'fbclid', 'gclid', 'msclkid', 'ref', 'source', '_ga', 'mc_cid', 'mc_eid'
        ]

    def normalize_url(self, url: str) -> str:
        parsed = urlparse(url)
        query_params = parse_qs(parsed.query)

        filtered_params = {
            k: v for k, v in query_params.items()
            if k.lower() not in self.tracking_params
        }

        new_query = urlencode(filtered_params, doseq=True)

        normalized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path.rstrip('/') if parsed.path != '/' else parsed.path,
            parsed.params,
            new_query,
            ''
        ))

        return normalized

    def get_proxy_config(self, proxy_group: Optional[str] = None) -> Optional[dict]:
        if not Config.BRIGHTDATA_PROXY_HOST:
            return None

        proxy_url = f"http://{Config.BRIGHTDATA_PROXY_USERNAME}:{Config.BRIGHTDATA_PROXY_PASSWORD}@{Config.BRIGHTDATA_PROXY_HOST}:{Config.BRIGHTDATA_PROXY_PORT}"

        return {
            'http://': proxy_url,
            'https://': proxy_url
        }

    def fetch_sitemap(self, url: str, etag: Optional[str] = None,
                      last_modified: Optional[str] = None,
                      proxy_group: Optional[str] = None) -> Tuple[Optional[bytes], Optional[str], Optional[str]]:
        headers = {
            'User-Agent': 'Mozilla/5.0 (compatible; ProductTrackerBot/1.0)'
        }

        if etag:
            headers['If-None-Match'] = etag
        if last_modified:
            headers['If-Modified-Since'] = last_modified

        proxies = self.get_proxy_config(proxy_group)

        try:
            with httpx.Client(proxies=proxies, timeout=30.0, follow_redirects=True) as client:
                response = client.get(url, headers=headers)

                if response.status_code == 304:
                    logger.info(f"Sitemap not modified: {url}")
                    return None, etag, last_modified

                response.raise_for_status()

                new_etag = response.headers.get('ETag')
                new_last_modified = response.headers.get('Last-Modified')

                content = response.content

                if url.endswith('.gz') or response.headers.get('Content-Encoding') == 'gzip':
                    try:
                        content = gzip.decompress(content)
                    except Exception:
                        pass

                return content, new_etag, new_last_modified

        except Exception as e:
            logger.error(f"Error fetching sitemap {url}: {e}")
            raise

    def parse_sitemap_index(self, content: bytes) -> List[str]:
        try:
            root = ET.fromstring(content)
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            sitemap_urls = []
            for sitemap in root.findall('.//ns:sitemap/ns:loc', ns):
                if sitemap.text:
                    sitemap_urls.append(sitemap.text.strip())

            return sitemap_urls
        except Exception as e:
            logger.error(f"Error parsing sitemap index: {e}")
            return []

    def parse_sitemap(self, content: bytes) -> List[Tuple[str, Optional[str]]]:
        try:
            root = ET.fromstring(content)
            ns = {'ns': 'http://www.sitemaps.org/schemas/sitemap/0.9'}

            urls = []
            for url_elem in root.findall('.//ns:url', ns):
                loc = url_elem.find('ns:loc', ns)
                lastmod = url_elem.find('ns:lastmod', ns)

                if loc is not None and loc.text:
                    url = loc.text.strip()
                    lastmod_val = lastmod.text.strip() if lastmod is not None and lastmod.text else None
                    urls.append((url, lastmod_val))

            return urls
        except Exception as e:
            logger.error(f"Error parsing sitemap: {e}")
            return []

    def is_sitemap_index(self, content: bytes) -> bool:
        try:
            root = etree.fromstring(content)
            return 'sitemapindex' in root.tag.lower()
        except Exception:
            return False

    def get_cache_key(self, sitemap_url: str) -> str:
        url_hash = hashlib.md5(sitemap_url.encode()).hexdigest()
        return f"sitemap_cache:{url_hash}"

    def get_cached_urls(self, sitemap_url: str) -> Optional[List[Tuple[str, Optional[str]]]]:
        cache_key = self.get_cache_key(sitemap_url)
        try:
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                import json
                return json.loads(cached_data)
        except Exception as e:
            logger.warning(f"Error reading cache: {e}")
        return None

    def cache_urls(self, sitemap_url: str, urls: List[Tuple[str, Optional[str]]], ttl: int = 3600):
        cache_key = self.get_cache_key(sitemap_url)
        try:
            import json
            self.redis_client.setex(cache_key, ttl, json.dumps(urls))
        except Exception as e:
            logger.warning(f"Error writing cache: {e}")

    def parse_all(self, sitemap_url: str, etag: Optional[str] = None,
                  last_modified: Optional[str] = None, proxy_group: Optional[str] = None,
                  use_cache: bool = True) -> Tuple[List[Tuple[str, Optional[str]]], Optional[str], Optional[str]]:

        if use_cache:
            cached = self.get_cached_urls(sitemap_url)
            if cached:
                logger.info(f"Using cached sitemap data for {sitemap_url}")
                return cached, etag, last_modified

        content, new_etag, new_last_modified = self.fetch_sitemap(
            sitemap_url, etag, last_modified, proxy_group
        )

        if content is None:
            cached = self.get_cached_urls(sitemap_url)
            if cached:
                return cached, new_etag, new_last_modified
            return [], new_etag, new_last_modified

        all_urls = []

        if self.is_sitemap_index(content):
            logger.info(f"Processing sitemap index: {sitemap_url}")
            sitemap_urls = self.parse_sitemap_index(content)

            for sub_sitemap_url in sitemap_urls:
                try:
                    sub_content, _, _ = self.fetch_sitemap(sub_sitemap_url, proxy_group=proxy_group)
                    if sub_content:
                        urls = self.parse_sitemap(sub_content)
                        all_urls.extend(urls)
                except Exception as e:
                    logger.error(f"Error processing sub-sitemap {sub_sitemap_url}: {e}")
        else:
            all_urls = self.parse_sitemap(content)

        normalized_urls = [
            (self.normalize_url(url), lastmod)
            for url, lastmod in all_urls
        ]

        if use_cache:
            self.cache_urls(sitemap_url, normalized_urls)

        return normalized_urls, new_etag, new_last_modified

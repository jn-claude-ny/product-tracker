from lxml import html
from typing import Any, Optional, List
import re
import json
import logging

logger = logging.getLogger(__name__)


class SelectorEngine:
    def __init__(self, html_content: str):
        self.tree = html.fromstring(html_content)

    def extract_css(self, selector: str) -> List[Any]:
        try:
            elements = self.tree.cssselect(selector)
            return elements
        except Exception as e:
            logger.error(f"CSS selector error: {e}")
            return []

    def extract_xpath(self, selector: str) -> List[Any]:
        try:
            elements = self.tree.xpath(selector)
            return elements
        except Exception as e:
            logger.error(f"XPath selector error: {e}")
            return []

    def extract(self, selector_type: str, selector_value: str) -> List[Any]:
        if selector_type == 'css':
            return self.extract_css(selector_value)
        elif selector_type == 'xpath':
            return self.extract_xpath(selector_value)
        else:
            logger.error(f"Unknown selector type: {selector_type}")
            return []

    @staticmethod
    def post_process(value: Any, process_type: Optional[str]) -> Optional[str]:
        if value is None:
            return None

        if isinstance(value, list):
            if not value:
                return None
            value = value[0]

        # Handle attribute extraction (e.g., attr:src, attr:href)
        if process_type and process_type.startswith('attr:'):
            attr_name = process_type.split(':', 1)[1]
            if hasattr(value, 'get'):
                attr_value = value.get(attr_name)
                return (
                    value.get_attribute('content') or
                    value.get_attribute('value') or
                    value.text_content().strip()
                ) if attr_value else None
            return None

        if hasattr(value, 'text_content'):
            text = value.text_content()
        elif isinstance(value, str):
            text = value
        else:
            text = str(value)

        text = text.strip()

        if not process_type:
            return text

        if process_type == 'clean_price':
            text = re.sub(r'[^\d.,]', '', text)
            text = text.replace(',', '.')
            parts = text.split('.')
            if len(parts) > 2:
                text = ''.join(parts[:-1]) + '.' + parts[-1]
            try:
                return str(float(text))
            except ValueError:
                return None

        elif process_type == 'extract_text':
            return text

        elif process_type == 'join':
            if hasattr(value, '__iter__') and not isinstance(value, str):
                return ' '.join([v.text_content() if hasattr(v, 'text_content') else str(v) for v in value])
            return text

        elif process_type == 'json_parse':
            try:
                return json.loads(text)
            except Exception:
                return None

        elif process_type == 'extract_number':
            numbers = re.findall(r'\d+\.?\d*', text)
            return numbers[0] if numbers else None

        elif process_type == 'lowercase':
            return text.lower()

        elif process_type == 'uppercase':
            return text.upper()

        elif process_type == 'strip_html':
            return re.sub(r'<[^>]+>', '', text)

        return text

    def extract_field(self, selector_type: str, selector_value: str,
                      post_process_type: Optional[str] = None) -> Optional[str]:
        elements = self.extract(selector_type, selector_value)

        if not elements:
            return None

        result = self.post_process(elements, post_process_type)
        return result

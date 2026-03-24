"""
parser.py — HTML parser using Python's html.parser stdlib module.
Extracts links, title, and visible body text from HTML documents.
"""

from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class LinkTextExtractor(HTMLParser):
    """Extract links, title, and visible text from an HTML page."""

    SKIP_TAGS = {"script", "style", "noscript", "iframe", "svg", "head"}

    def __init__(self, base_url=""):
        super().__init__()
        self.base_url = base_url
        self.links = []
        self.title = ""
        self.body_text_parts = []

        self._in_title = False
        self._skip_stack = 0  # depth of nested skip tags

    def handle_starttag(self, tag, attrs):
        tag_lower = tag.lower()

        if tag_lower in self.SKIP_TAGS:
            self._skip_stack += 1
            return

        if tag_lower == "title":
            self._in_title = True

        if tag_lower == "a":
            attrs_dict = dict(attrs)
            href = attrs_dict.get("href", "")
            if href:
                resolved = self._resolve_url(href)
                if resolved:
                    self.links.append(resolved)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()

        if tag_lower in self.SKIP_TAGS:
            self._skip_stack = max(0, self._skip_stack - 1)
            return

        if tag_lower == "title":
            self._in_title = False

    def handle_data(self, data):
        text = data.strip()
        if not text:
            return

        if self._in_title:
            self.title += text

        if self._skip_stack == 0:
            self.body_text_parts.append(text)

    def _resolve_url(self, href):
        """Resolve a URL reference to an absolute URL. Filter non-HTTP."""
        href = href.strip()

        # Skip anchors, javascript, mailto, tel, data URIs
        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "data:")):
            return None

        absolute = urljoin(self.base_url, href)
        parsed = urlparse(absolute)

        # Only allow http and https
        if parsed.scheme not in ("http", "https"):
            return None

        # Remove fragment
        clean = parsed._replace(fragment="").geturl()
        return clean

    def get_body_text(self):
        """Return cleaned body text as a single string."""
        return " ".join(self.body_text_parts)

    def error(self, message):
        """Override to suppress parser errors."""
        pass


def parse_html(html_content, base_url=""):
    """Parse HTML content and extract links, title, and body text.

    Returns:
        dict with keys: links (list[str]), title (str), body_text (str)
    """
    parser = LinkTextExtractor(base_url=base_url)
    try:
        parser.feed(html_content)
    except Exception:
        pass  # Tolerate malformed HTML

    return {
        "links": list(set(parser.links)),  # deduplicate links
        "title": parser.title.strip(),
        "body_text": parser.get_body_text(),
    }

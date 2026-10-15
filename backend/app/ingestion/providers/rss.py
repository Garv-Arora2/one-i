"""RSS/Atom news provider.

Parsed with the standard library XML parser: RSS is a simple format and does
not justify an extra dependency.
"""

from __future__ import annotations

import html
import logging
from xml.etree import ElementTree

import httpx

from app.analysis.textutils import domain_of, strip_html
from app.core.timeutil import parse_iso
from app.ingestion.default_feeds import outlet_name_for
from app.ingestion.providers.base import NewsProvider, RawArticle

logger = logging.getLogger(__name__)

_ATOM = "{http://www.w3.org/2005/Atom}"
_CONTENT = "{http://purl.org/rss/1.0/modules/content/}"
_DC = "{http://purl.org/dc/elements/1.1/}"
_USER_AGENT = "ONE-I/1.0 (news reader; RSS ingest)"


class RssNewsProvider(NewsProvider):
    name = "rss"

    def __init__(self, feed_urls: list[str], timeout: float = 15.0) -> None:
        self._feed_urls = feed_urls
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._feed_urls)

    def configuration_hint(self) -> str:
        if not self.is_configured():
            return "Set RSS_FEEDS to a comma-separated list of feed URLs."
        return f"{len(self._feed_urls)} feed(s) configured."

    def fetch_articles(self, query: str | None = None, limit: int = 50) -> list[RawArticle]:
        if not self.is_configured():
            return []
        articles: list[RawArticle] = []
        per_feed = max(1, limit // max(1, len(self._feed_urls)))
        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            for feed_url in self._feed_urls:
                try:
                    response = client.get(feed_url, headers={"User-Agent": _USER_AGENT})
                    if response.status_code == 429:
                        logger.warning("RSS feed rate limited: %s", feed_url)
                        continue
                    response.raise_for_status()
                    articles.extend(parse_feed(response.text, feed_url)[:per_feed])
                except (httpx.HTTPError, ElementTree.ParseError) as error:
                    logger.warning("RSS feed failed (%s): %s", feed_url, error)
        if query:
            needle = query.lower()
            articles = [
                article
                for article in articles
                if needle in article.title.lower() or needle in article.content.lower()
            ]
        return articles[:limit]


def _node_text(node: ElementTree.Element | None) -> str:
    if node is None:
        return ""
    return strip_html(html.unescape("".join(node.itertext()))).strip()


def _text(element: ElementTree.Element, *paths: str) -> str:
    for path in paths:
        found = element.find(path)
        text = _node_text(found)
        if text:
            return text
    return ""


def _item_link(item: ElementTree.Element) -> str:
    candidates = [_text(item, "link")]
    for path in ("link", f"{_ATOM}link"):
        node = item.find(path)
        if node is not None:
            candidates.append(node.attrib.get("href", ""))
    candidates.append(_text(item, "guid"))
    for candidate in candidates:
        url = candidate.strip()
        if url.startswith(("http://", "https://")):
            return url
    return ""


def _item_body(item: ElementTree.Element) -> str:
    parts = [
        _text(item, f"{_CONTENT}encoded"),
        _text(item, "description"),
        _text(item, f"{_ATOM}content"),
        _text(item, f"{_ATOM}summary"),
    ]
    nonempty = [part for part in parts if part]
    return max(nonempty, key=len) if nonempty else ""


def _article_content(title: str, body: str) -> str:
    if not body:
        return title
    if title.lower() in body.lower():
        return body
    return f"{title}. {body}"


def parse_feed(xml_text: str, feed_url: str) -> list[RawArticle]:
    """Parse an RSS 2.0 or Atom document into raw articles."""
    root = ElementTree.fromstring(xml_text)
    channel = root.find("channel")
    feed_title = _text(channel if channel is not None else root, "title", f"{_ATOM}title")
    items = list(root.iter("item")) + list(root.iter(f"{_ATOM}entry"))

    articles: list[RawArticle] = []
    for item in items:
        title = _text(item, "title", f"{_ATOM}title")
        link = _item_link(item)
        body = _item_body(item)
        published = parse_iso(
            _text(item, "pubDate", f"{_DC}date", f"{_ATOM}published", f"{_ATOM}updated")
        )
        if not title or not link:
            continue
        domain = domain_of(link) or domain_of(feed_url)
        articles.append(
            RawArticle(
                source_name=outlet_name_for(domain, feed_title or domain),
                source_domain=domain,
                title=title,
                url=link,
                content=_article_content(title, body),
                published_at=published,
                provider="rss",
            )
        )
    return articles

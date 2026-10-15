"""NewsAPI.org provider.

Requires NEWS_API_KEY. Handles rate limiting, error payloads and missing
fields; anything unusable is skipped and logged rather than guessed at.
"""

from __future__ import annotations

import logging

import httpx

from app.analysis.textutils import domain_of
from app.core.timeutil import parse_iso
from app.ingestion.providers.base import NewsProvider, ProviderError, RawArticle

logger = logging.getLogger(__name__)


class NewsApiProvider(NewsProvider):
    name = "newsapi"

    def __init__(self, api_key: str, base_url: str, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def configuration_hint(self) -> str:
        return "Configured." if self.is_configured() else "Set NEWS_API_KEY to enable NewsAPI."

    def fetch_articles(self, query: str | None = None, limit: int = 50) -> list[RawArticle]:
        if not self.is_configured():
            return []
        params = {
            "q": query or "*",
            "pageSize": min(limit, 100),
            "language": "en",
            "sortBy": "publishedAt",
        }
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    f"{self._base_url}/everything",
                    params=params,
                    headers={"X-Api-Key": self._api_key},
                )
        except httpx.HTTPError as error:
            raise ProviderError(f"NewsAPI request failed: {error}") from error

        if response.status_code == 429:
            raise ProviderError("NewsAPI rate limit reached.")
        if response.status_code == 401:
            raise ProviderError("NewsAPI rejected the configured key.")
        if response.status_code >= 400:
            raise ProviderError(f"NewsAPI returned HTTP {response.status_code}.")

        return parse_newsapi_payload(response.json())


def parse_newsapi_payload(payload: dict) -> list[RawArticle]:
    """Map a NewsAPI response body to raw articles, skipping unusable rows."""
    if not isinstance(payload, dict) or payload.get("status") != "ok":
        message = (payload or {}).get("message", "unknown error")
        raise ProviderError(f"NewsAPI error: {message}")

    articles: list[RawArticle] = []
    for item in payload.get("articles") or []:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url or not title:
            continue
        body = " ".join(
            part for part in [item.get("description"), item.get("content")] if part
        ).strip()
        source = item.get("source") or {}
        articles.append(
            RawArticle(
                source_name=(source.get("name") or domain_of(url)).strip(),
                source_domain=domain_of(url),
                title=title,
                url=url,
                content=body,
                published_at=parse_iso(item.get("publishedAt")),
                provider="newsapi",
            )
        )
    return articles

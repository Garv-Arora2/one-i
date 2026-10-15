"""GDELT DOC 2.1 provider (keyless global news inlet).

GDELT indexes broadcast, print and web news worldwide and exposes it without
an API key through the DOC 2.1 API. ONE I uses `artlist` mode, which returns
the original outlet URL, title, outlet name and first-seen time for each
match — never an aggregator copy. Bodies arrive later through the normal
enrich step, which fetches the original page.

Two uses:
- `fetch_articles`: recent coverage for one query (default rolling window).
- `fetch_range`: one explicit UTC window, used by `--backfill-days` to walk
  backwards week by week when recent news is too thin to compare.

Docs: https://blog.gdeltproject.org/gdelt-doc-2-0-api-debuts/
"""

from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta, timezone

import httpx

from app.analysis.textutils import domain_of
from app.core.timeutil import parse_iso
from app.ingestion.default_feeds import outlet_name_for
from app.ingestion.providers.base import NewsProvider, ProviderError, RawArticle

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.gdeltproject.org/api/v2/doc/doc"
_USER_AGENT = "ONE-I/1.0 (news reader; GDELT ingest)"
# GDELT throttles rapid-fire requests with HTTP 429. Every request waits for
# this long since the previous one, so routine runs and backfills stay polite.
# Kept high: GDELT has throttled this deployment aggressively in the past.
POLITENESS_SECONDS = 8.0

# Broad world-news queries used when GDELT_QUERIES is not set. Each one pulls
# widely reported stories; the grouping stage (not the query) decides what
# becomes an event, so overlapping queries only add corroboration.
DEFAULT_QUERIES: tuple[str, ...] = (
    "election",
    "ceasefire",
    "earthquake",
    "climate",
    "parliament",
    "summit",
    "sanctions",
    "outbreak",
)


def parse_seendate(value: str | None) -> datetime | None:
    """GDELT `seendate` looks like 20261011T153000Z; fall back to ISO."""
    if not value:
        return None
    text = value.strip()
    try:
        return datetime.strptime(text, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return parse_iso(text)


def _as_utc_compact(value: datetime) -> str:
    moment = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")


def parse_gdelt_payload(payload: dict) -> list[RawArticle]:
    """Map a GDELT artlist response to raw articles, skipping unusable rows."""
    if not isinstance(payload, dict):
        raise ProviderError("GDELT returned an unexpected response.")
    items = payload.get("articles")
    if not isinstance(items, list):
        message = payload.get("message", "unexpected response shape")
        raise ProviderError(f"GDELT error: {message}")

    articles: list[RawArticle] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        url = (item.get("url") or "").strip()
        title = (item.get("title") or "").strip()
        if not url.startswith(("http://", "https://")) or not title:
            continue
        domain = (item.get("domain") or domain_of(url)).lower().strip()
        source_name = (item.get("sourceCommonName") or "").strip() or outlet_name_for(
            domain, domain
        )
        articles.append(
            RawArticle(
                source_name=source_name,
                source_domain=domain or domain_of(url),
                title=title,
                url=url,
                content=title,
                published_at=parse_seendate(item.get("seendate")),
                provider="gdelt",
            )
        )
    return articles


class GdeltNewsProvider(NewsProvider):
    name = "gdelt"

    def __init__(
        self,
        enabled: bool = True,
        queries: list[str] | None = None,
        timespan: str = "7d",
        max_records: int = 100,
        timeout: float = 20.0,
    ) -> None:
        self._enabled = enabled
        self._queries = [query for query in (queries or []) if query.strip()] or list(
            DEFAULT_QUERIES
        )
        self._timespan = timespan
        self._max_records = max(1, min(max_records, 250))
        self._timeout = timeout
        self._last_call: float = 0.0

    def _polite_wait(self) -> None:
        gap = time.monotonic() - self._last_call
        if gap < POLITENESS_SECONDS:
            time.sleep(POLITENESS_SECONDS - gap)
        self._last_call = time.monotonic()

    def is_configured(self) -> bool:
        return self._enabled

    @property
    def queries(self) -> list[str]:
        return list(self._queries)

    def configuration_hint(self) -> str:
        if not self.is_configured():
            return "Set GDELT_ENABLED=true to enable the keyless GDELT inlet."
        return f"{len(self._queries)} querie(s), rolling {self._timespan} window."

    def _get(self, params: dict) -> dict:
        self._polite_wait()
        try:
            with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                response = client.get(
                    _BASE_URL, params=params, headers={"User-Agent": _USER_AGENT}
                )
        except httpx.HTTPError as error:
            raise ProviderError(f"GDELT request failed: {error}") from error
        if response.status_code == 429:
            # One patient retry: GDELT lifts short throttles within a minute.
            logger.warning("GDELT rate limited, waiting 60s before one retry.")
            time.sleep(60)
            self._polite_wait()
            try:
                with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
                    response = client.get(
                        _BASE_URL, params=params, headers={"User-Agent": _USER_AGENT}
                    )
            except httpx.HTTPError as error:
                raise ProviderError(f"GDELT request failed: {error}") from error
            if response.status_code == 429:
                raise ProviderError("GDELT rate limit reached.")
        if response.status_code >= 400:
            raise ProviderError(f"GDELT returned HTTP {response.status_code}.")
        try:
            payload = response.json()
        except ValueError as error:
            raise ProviderError("GDELT returned a non-JSON response.") from error
        return payload

    def _artlist_params(
        self,
        query: str,
        limit: int,
        extra: dict | None = None,
    ) -> dict:
        params: dict = {
            "query": query,
            "mode": "artlist",
            "format": "json",
            "maxrecords": min(limit, 250),
            "sort": "datedesc",
            "sourcelang": "english",
        }
        if extra:
            params.update(extra)
        return params

    def fetch_articles(self, query: str | None = None, limit: int = 50) -> list[RawArticle]:
        if not self.is_configured():
            return []
        queries = [query] if query else self._queries
        per_query = max(1, limit // max(1, len(queries)))
        collected: list[RawArticle] = []
        for item in queries:
            try:
                payload = self._get(
                    self._artlist_params(item, per_query, {"timespan": self._timespan})
                )
                collected.extend(parse_gdelt_payload(payload)[:per_query])
            except ProviderError as error:
                logger.warning("GDELT query failed (%s): %s", item, error)
        return collected[:limit]

    def fetch_range(
        self,
        query: str,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> list[RawArticle]:
        """Articles matching `query` first seen inside [start, end]."""
        payload = self._get(
            self._artlist_params(
                query,
                limit,
                {
                    "startdatetime": _as_utc_compact(start),
                    "enddatetime": _as_utc_compact(end),
                },
            )
        )
        return parse_gdelt_payload(payload)[:limit]

    def backfill_windows(
        self, days: int, chunk_days: int = 7
    ) -> list[tuple[datetime, datetime]]:
        """Split the last `days` into [start, end] UTC windows, newest first."""
        now = datetime.now(timezone.utc)
        windows: list[tuple[datetime, datetime]] = []
        remaining = max(1, days)
        cursor = now
        while remaining > 0:
            span = min(chunk_days, remaining)
            start = cursor - timedelta(days=span)
            windows.append((start, cursor))
            cursor = start
            remaining -= span
        return windows

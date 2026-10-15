"""Ingestion pipeline: collect -> validate -> normalise -> deduplicate -> store.

Provider failures are captured in the report; one broken feed never aborts a
run and never results in invented data.
"""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from app.ingestion.dedupe import deduplicate
from app.ingestion.normalize import normalize_batch
from app.ingestion.providers.base import (
    IngestionReport,
    NewsProvider,
    ProviderError,
    RawArticle,
)
from app.ingestion.store import store_articles

logger = logging.getLogger(__name__)


def collect_articles(
    providers: list[NewsProvider], query: str | None, limit_per_provider: int
) -> tuple[list[RawArticle], list[str]]:
    """Fetch from every configured provider, collecting failures as messages."""
    collected: list[RawArticle] = []
    errors: list[str] = []
    for provider in providers:
        if not provider.is_configured():
            continue
        try:
            collected.extend(provider.fetch_articles(query=query, limit=limit_per_provider))
        except ProviderError as error:
            logger.warning("Provider %s failed: %s", provider.name, error)
            errors.append(f"{provider.name}: {error}")
        except Exception as error:  # defensive: a provider must not stop the run
            logger.exception("Provider %s raised an unexpected error", provider.name)
            errors.append(f"{provider.name}: unexpected error ({error})")
    return collected, errors


def ingest_articles(
    session: Session,
    providers: list[NewsProvider],
    *,
    query: str | None = None,
    limit_per_provider: int = 50,
) -> IngestionReport:
    """Run the full pipeline for news articles."""
    raw_articles, errors = collect_articles(providers, query, limit_per_provider)
    normalized, rejected = normalize_batch(raw_articles)
    unique, duplicates = deduplicate(normalized)
    report = store_articles(session, unique)
    report.fetched = len(raw_articles)
    report.invalid = len(rejected)
    report.duplicates = len(duplicates)
    report.errors = errors
    for item in rejected:
        logger.info("Rejected article %s: %s", item.url, item.reason)
    return report

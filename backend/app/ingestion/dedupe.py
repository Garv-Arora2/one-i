"""Duplicate detection for ingested articles.

Three deterministic checks, cheapest first: identical canonical URL, identical
content fingerprint, then a near-identical title from the same source (the
usual "story updated, republished" case).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.analysis.textutils import token_set
from app.core.timeutil import as_utc
from app.ingestion.normalize import NormalizedArticle

NEAR_DUPLICATE_TITLE_OVERLAP = 0.9
_EPOCH = as_utc(datetime(1970, 1, 1))


@dataclass(frozen=True)
class DuplicateArticle:
    url: str
    reason: str
    duplicate_of: str


def _is_near_duplicate_title(left: NormalizedArticle, right: NormalizedArticle) -> bool:
    if left.source_domain != right.source_domain:
        return False
    left_tokens, right_tokens = token_set(left.title), token_set(right.title)
    if not left_tokens or not right_tokens:
        return False
    shared = len(left_tokens & right_tokens)
    return shared / max(len(left_tokens), len(right_tokens)) >= NEAR_DUPLICATE_TITLE_OVERLAP


def deduplicate(
    articles: list[NormalizedArticle],
) -> tuple[list[NormalizedArticle], list[DuplicateArticle]]:
    """Keep the earliest published version of each story."""
    ordered = sorted(
        articles,
        key=lambda article: (as_utc(article.published_at) is None, as_utc(article.published_at) or _EPOCH, article.url),
    )
    unique: list[NormalizedArticle] = []
    duplicates: list[DuplicateArticle] = []
    seen_urls: dict[str, str] = {}
    seen_hashes: dict[str, str] = {}

    for article in ordered:
        if article.url in seen_urls:
            duplicates.append(
                DuplicateArticle(article.url, "same url", seen_urls[article.url])
            )
            continue
        if article.content_hash and article.content_hash in seen_hashes:
            duplicates.append(
                DuplicateArticle(article.url, "identical text", seen_hashes[article.content_hash])
            )
            continue
        near = next(
            (kept for kept in unique if _is_near_duplicate_title(kept, article)), None
        )
        if near is not None:
            duplicates.append(
                DuplicateArticle(article.url, "near-identical title from same source", near.url)
            )
            continue

        unique.append(article)
        seen_urls[article.url] = article.url
        if article.content_hash:
            seen_hashes[article.content_hash] = article.url

    return unique, duplicates

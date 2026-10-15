"""Validation and normalisation of raw ingested articles.

Malformed or too-thin payloads are rejected with a reason instead of being
patched up with invented values.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.analysis.textutils import (
    STOPWORDS,
    canonicalize_url,
    clean_text,
    content_fingerprint,
    domain_of,
    normalize_title,
    tokenize,
)
from app.core.timeutil import as_utc
from app.ingestion.providers.base import RawArticle

MIN_TITLE_CHARS = 12
MIN_CONTENT_CHARS = 80

# Every analysis lexicon is English (action verbs, aspect words, stopwords),
# so non-English rows would silently poison grouping and comparisons. A row
# passes when its title and body share at least two distinct core English
# function words, one of them longer than two letters: single short words
# ("in", "we", "to") also occur in Dutch, German or French, but a second,
# longer match ("after", "said", "which") all but guarantees English prose.
# Single-letter words are excluded entirely: "a" is also an Italian word.
CORE_ENGLISH_WORDS = frozenset(
    """
the and of to in on as at by for with was were are been be has have had
said says after from that this these those will would can could should
over before between about into during more than when while because their
there then such only also who what which where how not but if or they
them his her its our your he she we you him us my do does did so up out
off all any is it
""".split()
)
MIN_CORE_ENGLISH_WORDS = 2
MIN_CORE_ENGLISH_LONG_LEN = 3
# Share of tokens that must be English stopwords. Long foreign-language
# bodies can contain a few accidental lookalikes ("do", "her", "in"), but
# only real English prose is dense with them.
MIN_STOPWORD_DENSITY = 0.10


def is_english_reporting(title: str, content: str) -> bool:
    """True when the text carries enough core English function words.

    Every analysis lexicon is English, so this guards grouping, coverage,
    numbers and wording against non-English rows. Deliberate word lists, not
    a language model; see CORE_ENGLISH_WORDS for why the bar is shaped so.
    """
    tokens = [token for token in tokenize(f"{title or ''} {content or ''}") if len(token) > 1]
    if not tokens:
        return False
    core_words = {token for token in tokens if token in CORE_ENGLISH_WORDS}
    if len(core_words) < MIN_CORE_ENGLISH_WORDS or not any(
        len(word) >= MIN_CORE_ENGLISH_LONG_LEN for word in core_words
    ):
        return False
    stopwords = sum(1 for token in tokens if token in STOPWORDS)
    return stopwords / len(tokens) >= MIN_STOPWORD_DENSITY


@dataclass(frozen=True)
class NormalizedArticle:
    source_name: str
    source_domain: str
    source_type: str
    title: str
    url: str
    content: str
    published_at: datetime | None
    content_hash: str
    provider: str
    is_demo: bool


@dataclass(frozen=True)
class RejectedArticle:
    url: str
    reason: str


def normalize_article(raw: RawArticle) -> NormalizedArticle | RejectedArticle:
    """Clean one raw article, or explain why it cannot be used."""
    url = canonicalize_url(raw.url)
    if not url.startswith(("http://", "https://")):
        return RejectedArticle(url=raw.url or "", reason="missing or invalid url")

    title = normalize_title(raw.title)
    if len(title) < MIN_TITLE_CHARS:
        return RejectedArticle(url=url, reason="missing or too short title")

    content = clean_text(raw.content)
    if len(content) < MIN_CONTENT_CHARS:
        return RejectedArticle(url=url, reason="article text too short to analyse")

    core_words = {token for token in tokenize(f"{title} {content}") if token in CORE_ENGLISH_WORDS}
    has_long_word = any(len(word) >= MIN_CORE_ENGLISH_LONG_LEN for word in core_words)
    if not is_english_reporting(title, content):
        return RejectedArticle(url=url, reason="article text is not English reporting")

    domain = (raw.source_domain or domain_of(url)).lower().strip()
    if domain.startswith("www."):
        domain = domain[4:]
    if not domain:
        return RejectedArticle(url=url, reason="missing source domain")

    return NormalizedArticle(
        source_name=clean_text(raw.source_name) or domain,
        source_domain=domain,
        source_type=raw.source_type or "news_outlet",
        title=title,
        url=url,
        content=content,
        published_at=as_utc(raw.published_at),
        content_hash=content_fingerprint(title, content),
        provider=raw.provider,
        is_demo=raw.is_demo,
    )


def normalize_batch(
    raws: list[RawArticle],
) -> tuple[list[NormalizedArticle], list[RejectedArticle]]:
    accepted: list[NormalizedArticle] = []
    rejected: list[RejectedArticle] = []
    for raw in raws:
        result = normalize_article(raw)
        if isinstance(result, NormalizedArticle):
            accepted.append(result)
        else:
            rejected.append(result)
    return accepted, rejected

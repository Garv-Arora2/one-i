"""Fetch fuller article text from the original URL.

RSS items usually carry only a headline and a short blurb. Coverage, numbers
and wording need the body of the report. This module asks each outlet for the
page at the stored URL, extracts readable paragraphs, and replaces the stored
blurb when the page text is substantially longer.

Sites that refuse the request (paywalls, bot blocks) are left unchanged —
ONE I never invents missing text.
"""

from __future__ import annotations

import logging
import re
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.analysis.textutils import clean_text, content_fingerprint
from app.ingestion.normalize import is_english_reporting
from app.models import Article

logger = logging.getLogger(__name__)

_USER_AGENT = "ONE-I/1.0 (news reader; article enrich)"
# Only enrich blurbs. Longer bodies are already worth analysing.
THIN_CONTENT_CHARS = 500
MIN_EXTRACTED_CHARS = 400
MAX_BODY_CHARS = 12_000

_SKIP_TAGS = frozenset(
    {
        "script",
        "style",
        "noscript",
        "svg",
        "nav",
        "footer",
        "header",
        "aside",
        "form",
        "iframe",
        "button",
        "template",
    }
)
_BLOCK_TAGS = frozenset({"p", "h1", "h2", "h3", "h4", "li", "blockquote", "figcaption"})
_BOILERPLATE = re.compile(
    r"(cookie|subscribe|sign in|sign up|newsletter|advertisement|enable javascript|"
    r"related stories|share this|follow us|all rights reserved|terms of (use|service)|"
    r"privacy policy|we use cookies|skip to main content|browser extension|"
    r"cover image|issued on|does not exist|not available anymore|"
    r"to watch this content|disable it on this site|last updated|"
    r"posted \w+ \d|listen \d+ min|estimated (read|\d+ min)|ai-?generated|"
    r"mispronunciation)",
    re.IGNORECASE,
)
# "Related stories" rails share identical headline lists across unrelated
# articles from the same outlet, which once chained hurricanes into a Riyadh
# airport story. Skip those blocks structurally by their markup, whatever
# words they happen to contain.
_CHROME_CLASS = re.compile(
    r"(related|read-?more|recommended|trending|most-?read|most-?popular|"
    r"sidebar|rail|more-?from|also-?read|teasers?|outbrain|taboola|"
    r"newsletter|share-?tools|author-?bio|breadcrumb|video-player|"
    r"live-blog-cta|up-next|next-story)",
    re.IGNORECASE,
)
_CHROME_TAGS = frozenset({"div", "section", "aside", "nav", "ul", "ol"})


@dataclass
class EnrichmentReport:
    considered: int = 0
    updated: int = 0
    skipped_thin_page: int = 0
    skipped_non_english: int = 0
    failed: int = 0


class _ParagraphExtractor(HTMLParser):
    """Collect paragraph-like text while skipping chrome and scripts."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._skip_stack: list[str] = []
        self._buffer: list[str] = []
        self.chunks: list[str] = []

    def _is_chrome_block(self, tag: str, attrs) -> bool:
        if tag not in _CHROME_TAGS:
            return False
        for name, value in attrs:
            if name in ("class", "id") and value and _CHROME_CLASS.search(value):
                return True
        return False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in _SKIP_TAGS or self._is_chrome_block(tag, attrs):
            self._skip_stack.append(tag)
            return
        if self._skip_stack:
            return
        if tag in _BLOCK_TAGS or tag == "br":
            self._flush()

    def handle_endtag(self, tag: str) -> None:
        if self._skip_stack and tag == self._skip_stack[-1]:
            self._skip_stack.pop()
            return
        if self._skip_stack:
            return
        if tag in _BLOCK_TAGS:
            self._flush()

    def handle_data(self, data: str) -> None:
        if self._skip_stack:
            return
        text = data.strip()
        if text:
            self._buffer.append(text)

    def _flush(self) -> None:
        if not self._buffer:
            return
        chunk = " ".join(self._buffer).strip()
        self._buffer.clear()
        if len(chunk) >= 40 and not _BOILERPLATE.search(chunk):
            self.chunks.append(chunk)


def extract_article_text(html: str) -> str:
    """Turn an HTML page into a plain-text article body."""
    if not html:
        return ""
    parser = _ParagraphExtractor()
    try:
        parser.feed(html)
        parser.close()
    except Exception:
        return ""
    paragraphs = parser.chunks
    if not paragraphs:
        return ""
    # Drop a leading site-chrome title line when the next paragraphs are longer.
    if len(paragraphs) >= 2 and len(paragraphs[0]) < 120:
        paragraphs = paragraphs[1:]
    body = clean_text(" ".join(paragraphs))
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS].rsplit(" ", 1)[0]
    return body


def fetch_article_text(url: str, *, timeout: float = 20.0) -> str | None:
    """Download one article page and extract its body, or None on failure."""
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url, headers={"User-Agent": _USER_AGENT})
        if response.status_code >= 400:
            logger.info("Article page refused (%s): %s", response.status_code, url)
            return None
        content_type = (response.headers.get("content-type") or "").lower()
        if "html" not in content_type and "text/" not in content_type:
            return None
        return extract_article_text(response.text)
    except httpx.HTTPError as error:
        logger.info("Article page failed (%s): %s", url, error)
        return None


_CHROME_MARKERS = (
    "skip to main content",
    "cover image",
    "issued on:",
    "browser extension",
    "does not exist or is not available",
)


def repair_chrome_bodies(session: Session, *, is_demo: bool = False) -> list[int]:
    """Reset bodies poisoned by site chrome back to title stubs.

    Stored bodies captured before related-story rails were filtered share
    identical headline lists across unrelated articles, which chained
    unrelated stories into one event. Reset articles match visible chrome
    markers; the caller re-enriches exactly these ids with the fixed
    extractor. Returns the reset article ids.
    """
    conditions = [Article.content.ilike(f"%{marker}%") for marker in _CHROME_MARKERS]
    polluted = list(
        session.scalars(
            select(Article).where(Article.is_demo == is_demo, or_(*conditions))
        )
    )
    for article in polluted:
        title = article.title or ""
        article.content = title
        article.content_hash = content_fingerprint(title, title)
    session.flush()
    return [article.id for article in polluted]


def enrich_articles(
    session: Session,
    *,
    is_demo: bool = False,
    limit: int = 200,
    timeout: float = 20.0,
    only_ids: set[int] | None = None,
    workers: int = 8,
) -> EnrichmentReport:
    """Replace thin stored blurbs with fuller page text where available.

    Pages are downloaded concurrently (network-bound); every database change
    still happens on this thread, in article order.
    """
    report = EnrichmentReport()
    statement = (
        select(Article)
        .where(Article.is_demo == is_demo)
        .order_by(Article.id.desc())
        .limit(limit)
    )
    if only_ids is not None:
        statement = select(Article).where(
            Article.is_demo == is_demo, Article.id.in_(only_ids)
        )
    articles = [
        article
        for article in session.scalars(statement)
        if len(article.content or "") < THIN_CONTENT_CHARS
    ]
    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        bodies = list(
            pool.map(lambda url: fetch_article_text(url, timeout=timeout), [a.url for a in articles])
        )
    for article, body in zip(articles, bodies):
        report.considered += 1
        if body is None:
            report.failed += 1
            continue
        if len(body) < MIN_EXTRACTED_CHARS or len(body) <= len(article.content or "") + 80:
            report.skipped_thin_page += 1
            continue
        title = article.title or ""
        if not is_english_reporting(title, body):
            # A non-English page (syndicated regional edition, wrong URL):
            # keep the English stub rather than poisoning analysis.
            report.skipped_non_english += 1
            continue
        if article.ingest_provider == "currentevents":
            # The stored title is Wikipedia's one-line summary, not the
            # outlet's words, so only the outlet's own page text is kept.
            combined = body
        else:
            combined = body if title.lower() in body.lower() else f"{title}. {body}"
        article.content = combined
        article.content_hash = content_fingerprint(title, combined)
        report.updated += 1
    session.flush()
    return report


# A "related stories" rail repeats identical headline lists across every
# article page of an outlet. Once stored, unrelated stories share text and get
# chained into one event. Only enriched bodies are scrubbed: short stubs are
# the story text itself and must keep every sentence.
#
# Rails are often NOT period-separated ("...released Saudi-led coalition
# says..."), so sentence-exact matching misses them. Instead we flag repeated
# 8-word phrases: eight specific words in a row almost never coincide by
# chance, but rails repeat them verbatim. Any sentence containing a flagged
# phrase is removed from long bodies.
SCRUB_MIN_BODY_CHARS = 500
SCRUB_PHRASE_WORDS = 8
# Three outlets carrying one wire paragraph is normal; but a phrase shared
# across three long bodies is usually an outlet rail or transcript chrome
# (rails rotate daily, so the same rail rarely reaches four). Stubs are exempt.
SCRUB_MIN_DOCS = 3


def normalize_sentence(sentence: str) -> str:
    """Canonical form for repeat detection (pure function)."""
    return re.sub(r"\s+", " ", (sentence or "").lower()).strip()


def _word_phrases(text: str, words: int = SCRUB_PHRASE_WORDS) -> set[str]:
    tokens = normalize_sentence(text).split(" ")
    return {" ".join(tokens[i : i + words]) for i in range(len(tokens) - words + 1)}


def find_repeated_sentences(
    bodies: dict[int, str], min_docs: int = SCRUB_MIN_DOCS
) -> dict[str, set[int]]:
    """8-word phrases appearing in `min_docs` or more long bodies.

    Returns each phrase mapped to the bodies containing it. Pure function.
    """
    docs: dict[str, set[int]] = {}
    for article_id, body in bodies.items():
        if len(body or "") < SCRUB_MIN_BODY_CHARS:
            continue
        for phrase in _word_phrases(body):
            docs.setdefault(phrase, set()).add(article_id)
    return {key: ids for key, ids in docs.items() if len(ids) >= min_docs}


def scrub_repeated_sentences(
    session: Session, *, is_demo: bool = False, min_docs: int = SCRUB_MIN_DOCS
) -> tuple[int, int]:
    """Remove outlet-rail phrases shared across many bodies.

    Returns (articles changed, sentences removed). Deterministic and
    reported, never silent: the caller prints both numbers.
    """
    from app.analysis.textutils import split_sentences

    articles = list(
        session.scalars(select(Article).where(Article.is_demo == is_demo))
    )
    repeated = find_repeated_sentences(
        {article.id: article.content or "" for article in articles}, min_docs
    )
    if not repeated:
        return 0, 0
    phrases = set(repeated)

    def is_rail(sentence: str) -> bool:
        words = normalize_sentence(sentence).split(" ")
        return any(
            " ".join(words[i : i + SCRUB_PHRASE_WORDS]) in phrases
            for i in range(len(words) - SCRUB_PHRASE_WORDS + 1)
        )

    changed = 0
    removed = 0
    for article in articles:
        body = article.content or ""
        if len(body) < SCRUB_MIN_BODY_CHARS:
            continue
        sentences = split_sentences(body)
        kept = [sentence for sentence in sentences if not is_rail(sentence)]
        if len(kept) != len(sentences):
            removed += len(sentences) - len(kept)
            title = article.title or ""
            new_body = " ".join(kept).strip()
            article.content = f"{title}. {new_body}" if new_body else title
            article.content_hash = content_fingerprint(title, article.content)
            changed += 1
    session.flush()
    return changed, removed

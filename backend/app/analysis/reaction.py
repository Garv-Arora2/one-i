"""Public reaction aggregation.

Reddit and YouTube discussion is shown as the most-liked comments that are
actually about the event. It is supplementary context: popularity is never
treated as evidence that something is true, and no account-level inference is
made.

A comment counts as relevant when it is readable English of a few words, has
no link, and shares at least one meaningful word with the event's headline or
summary. Everything else (emoji, "first!", links, other topics) is left out.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.analysis.textutils import STOPWORDS, content_tokens, tokenize
from app.core.timeutil import as_utc

MIN_COMMENT_WORDS = 4
# Shorter words ("war", "say") match too many unrelated comments.
MIN_EVENT_TERM_LENGTH = 4


@dataclass(frozen=True)
class ReactionItem:
    id: int
    platform: str
    content: str
    published_at: datetime | None = None
    engagement: int = 0
    url: str | None = None
    community: str | None = None


@dataclass
class ReactionSummary:
    available: bool
    total: int
    by_platform: dict[str, dict[str, int]]
    timeline: list[dict[str, object]]
    highlights: list[ReactionItem] = field(default_factory=list)
    unavailable_reason: str | None = None


def looks_english(text: str) -> bool:
    """Enough words, at least one common English function word, and mostly Latin letters."""
    words = tokenize(text)
    if len(words) < MIN_COMMENT_WORDS or not any(word in STOPWORDS for word in words):
        return False
    letters = [char for char in text if char.isalpha()]
    return bool(letters) and sum(char.isascii() for char in letters) / len(letters) >= 0.8


def event_terms(*texts: str) -> set[str]:
    """Meaningful words from the event's headline and summary."""
    return {
        token
        for text in texts
        for token in content_tokens(text or "")
        if len(token) >= MIN_EVENT_TERM_LENGTH
    }


def is_relevant(item: ReactionItem, terms: set[str]) -> bool:
    text = item.content
    if "http" in text.lower() or not looks_english(text):
        return False
    return bool(terms & set(content_tokens(text)))


def deduplicate_reactions(items: list[ReactionItem]) -> list[ReactionItem]:
    """Drop repeated posts, keeping the first occurrence of each text."""
    seen: set[tuple[str, str]] = set()
    unique: list[ReactionItem] = []
    for item in items:
        fingerprint = (item.platform, " ".join(content_tokens(item.content))[:200])
        if not fingerprint[1] or fingerprint in seen:
            continue
        seen.add(fingerprint)
        unique.append(item)
    return unique


def aggregate_reactions(
    items: list[ReactionItem], terms: set[str], *, highlight_limit: int = 6
) -> ReactionSummary:
    """Volume, timing and the most-liked comments about the event."""
    unique = deduplicate_reactions(items)
    if not unique:
        return ReactionSummary(
            available=False,
            total=0,
            by_platform={},
            timeline=[],
            unavailable_reason="No public discussion has been collected for this event.",
        )

    by_platform: dict[str, dict[str, int]] = {}
    for item in unique:
        bucket = by_platform.setdefault(item.platform, {"posts": 0, "engagement": 0})
        bucket["posts"] += 1
        bucket["engagement"] += max(0, item.engagement)

    day_counts: Counter[str] = Counter()
    for item in unique:
        published = as_utc(item.published_at)
        if published:
            day_counts[published.date().isoformat()] += 1
    timeline = [{"date": day, "posts": count} for day, count in sorted(day_counts.items())]

    relevant = [item for item in unique if is_relevant(item, terms)]
    highlights = sorted(relevant, key=lambda item: (-item.engagement, item.id))[:highlight_limit]

    return ReactionSummary(
        available=True,
        total=len(unique),
        by_platform=by_platform,
        timeline=timeline,
        highlights=highlights,
    )

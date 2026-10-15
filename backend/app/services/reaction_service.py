"""Collect public reaction (YouTube comments, Reddit when configured) for live events.

Runs as a CLI job after analysis, never during a page request. Each event is
searched with a short phrase and only within a window around the event, so
comments come from videos about this event rather than from later, unrelated
coverage of the same place or person.
"""

from __future__ import annotations

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analysis.textutils import CRUMB_SEPARATOR, STOPWORDS, TOPIC_SEPARATOR
from app.core.timeutil import as_utc
from app.db.base import utcnow
from app.ingestion.providers.base import ProviderError, ReactionProvider
from app.ingestion.store import store_reactions
from app.models import Article, Event, PublicReaction

logger = logging.getLogger(__name__)

WINDOW_BEFORE = timedelta(days=1)
WINDOW_AFTER = timedelta(days=10)
QUERY_MAX_WORDS = 6
# A topic must be shared by this many of the event's articles to be trusted.
TOPIC_MIN_ARTICLES = 2
# A topic reported on this many different days is an ongoing story ("2026 Iran
# war"), so the search is pinned to this event with names from its headline.
ONGOING_TOPIC_MIN_DAYS = 4
ANCHOR_COUNT = 2

_YEAR_PREFIX = re.compile(r"^(?:\d{4}(?:[–-]\d{2,4})?\s+)+")
_WORD = re.compile(r"[A-Za-z][A-Za-z'’\-]*")
_FILLER = frozenset(
    {"least", "among", "amid"}
    | {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}
)


@dataclass
class ReactionRefreshReport:
    events_considered: int = 0
    events_skipped: int = 0
    events_searched: int = 0
    stored: int = 0
    errors: list[str] = field(default_factory=list)
    queries: dict[int, str] = field(default_factory=dict)


@dataclass(frozen=True)
class SearchPlan:
    query: str
    anchors: tuple[str, ...] = ()


def breadcrumb_topic(content: str) -> str | None:
    """Deepest Wikipedia topic of one current-events article, year prefix removed."""
    head, separator, _ = (content or "").partition(CRUMB_SEPARATOR)
    if not separator or TOPIC_SEPARATOR not in head or len(head) > 300:
        return None
    topic = _YEAR_PREFIX.sub("", head.split(TOPIC_SEPARATOR)[-1]).strip()
    return topic if len(topic) >= 4 else None


def topic_from_breadcrumbs(contents: list[str]) -> str | None:
    """Most frequent deepest topic, if enough of the event's articles share it."""
    topics = Counter(topic for topic in map(breadcrumb_topic, contents) if topic)
    if not topics:
        return None
    topic, count = topics.most_common(1)[0]
    return topic if count >= TOPIC_MIN_ARTICLES else None


def _headline_words(title: str) -> list[str]:
    words = [match.group(0) for match in _WORD.finditer(title or "")]
    return [w for w in words if len(w) > 2 and w.lower() not in STOPWORDS | _FILLER]


def query_from_title(title: str) -> str:
    """Up to six key words of the headline, proper nouns first, in headline order."""
    keep = _headline_words(title)
    proper = {i for i, w in enumerate(keep) if w[0].isupper() and i > 0}
    ranked = sorted(range(len(keep)), key=lambda i: (i not in proper, i))[:QUERY_MAX_WORDS]
    return " ".join(keep[i] for i in sorted(ranked))


def headline_anchors(title: str, topic: str, word_frequency: Counter[str]) -> tuple[str, ...]:
    """The rarest capitalised headline words not already in the topic."""
    topic_words = {word.lower() for word in _WORD.findall(topic)}
    candidates: list[str] = []
    for index, word in enumerate(_headline_words(title)):
        if index == 0 or not word[0].isupper() or word.lower() in topic_words:
            continue
        if word not in candidates:
            candidates.append(word)
    rarest = sorted(candidates, key=lambda w: word_frequency.get(w.lower(), 0))[:ANCHOR_COUNT]
    return tuple(w for w in candidates if w in rarest)


def plan_search(
    title: str,
    contents: list[str],
    ongoing_topics: set[str] = frozenset(),
    word_frequency: Counter[str] | None = None,
) -> SearchPlan:
    topic = topic_from_breadcrumbs(contents)
    if topic is None:
        return SearchPlan(query_from_title(title))
    if topic not in ongoing_topics:
        return SearchPlan(topic)
    anchors = headline_anchors(title, topic, word_frequency or Counter())
    return SearchPlan(" ".join([topic, *anchors]), anchors)


def event_search_query(title: str, contents: list[str]) -> str:
    return plan_search(title, contents).query


def ongoing_topics(rows: list[tuple[str, object]]) -> set[str]:
    """Topics reported on ONGOING_TOPIC_MIN_DAYS or more different days."""
    days: dict[str, set] = {}
    for content, published_at in rows:
        topic = breadcrumb_topic(content)
        moment = as_utc(published_at)
        if topic and moment:
            days.setdefault(topic, set()).add(moment.date())
    return {topic for topic, seen in days.items() if len(seen) >= ONGOING_TOPIC_MIN_DAYS}


def headline_word_frequency(titles: list[str]) -> Counter[str]:
    frequency: Counter[str] = Counter()
    for title in titles:
        frequency.update({word.lower() for word in _WORD.findall(title or "")})
    return frequency


def refresh_live_reactions(
    session: Session,
    providers: list[ReactionProvider],
    *,
    refresh: bool = False,
    limit: int = 300,
) -> ReactionRefreshReport:
    """Fetch and store reactions for every published live event.

    Events that already have reactions are skipped unless ``refresh`` is set,
    which keeps a daily run inside the YouTube quota.
    """
    report = ReactionRefreshReport()
    if not providers:
        return report
    events = list(session.scalars(select(Event).where(Event.is_demo.is_(False)).order_by(Event.id)))
    existing = dict(
        session.execute(
            select(PublicReaction.event_id, func.count(PublicReaction.id))
            .where(PublicReaction.is_demo.is_(False))
            .group_by(PublicReaction.event_id)
        ).all()
    )
    corpus = session.execute(
        select(Article.title, Article.content, Article.published_at).where(
            Article.is_demo.is_(False)
        )
    ).all()
    ongoing = ongoing_topics([(content, published) for _, content, published in corpus])
    frequency = headline_word_frequency([title for title, _, _ in corpus])
    now = utcnow()
    for event in events:
        report.events_considered += 1
        if existing.get(event.id) and not refresh:
            report.events_skipped += 1
            continue
        contents = list(session.scalars(select(Article.content).where(Article.event_id == event.id)))
        plan = plan_search(event.title, contents, ongoing, frequency)
        report.queries[event.id] = plan.query + (
            f"  (must mention: {', '.join(plan.anchors)})" if plan.anchors else ""
        )
        event_time = as_utc(event.event_time)
        since = event_time - WINDOW_BEFORE if event_time else None
        until = min(event_time + WINDOW_AFTER, now) if event_time else None
        if refresh:
            session.execute(delete(PublicReaction).where(PublicReaction.event_id == event.id))
        report.events_searched += 1
        for provider in providers:
            try:
                raw = provider.fetch_reactions(
                    plan.query, limit, since=since, until=until, anchors=plan.anchors
                )
            except ProviderError as error:
                report.errors.append(f"{provider.name} ({event.slug}): {error}")
                if "quota" in str(error).lower():
                    session.commit()
                    return report
                continue
            report.stored += store_reactions(session, event.id, raw).stored
        session.commit()
    return report

"""Event grouping.

Decides which articles describe the same event using four explainable signals:
body/lead similarity (TF-IDF cosine), shared entities, title word overlap and
time proximity. Articles are linked pairwise and connected groups become events.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.analysis.entities import entity_set
from app.analysis.textutils import (
    build_tfidf_matrix,
    clean_text,
    cosine_matrix,
    jaccard,
    normalize_title,
    token_set,
    top_terms,
)
from app.analysis.thresholds import GROUPING, GroupingConfig
from app.core.timeutil import as_utc, hours_between

LEAD_CHARACTERS = 900

# A name seen in more articles than this is too widespread to identify one
# story, no matter how large the archive grows.
_COMMON_ENTITY_MIN_DOCS = 10

# Country-scale names that appear in many unrelated stories. Sharing only
# these is not enough evidence that two articles describe the same event.
_GENERIC_ENTITIES = frozenset(
    {
        "africa",
        "african",
        "america",
        "american",
        "asia",
        "asian",
        "australia",
        "australian",
        "britain",
        "british",
        "canada",
        "canadian",
        "china",
        "chinese",
        "egypt",
        "egyptian",
        "europe",
        "european",
        "france",
        "french",
        "germany",
        "german",
        "gaza",
        "india",
        "indian",
        "iran",
        "iranian",
        "iraq",
        "iraqi",
        "israel",
        "israeli",
        "japan",
        "japanese",
        "korea",
        "korean",
        "mexico",
        "mexican",
        "russia",
        "russian",
        "saudi",
        "saudi arabia",
        "south africa",
        "south african",
        "south africans",
        "sudan",
        "sudanese",
        "syria",
        "syrian",
        "turkey",
        "turkish",
        "ukraine",
        "ukrainian",
        "united kingdom",
        "united states",
        "yemen",
        "yemeni",
        "u.s",
        "u.s.",
        "us",
        "u.k",
        "u.k.",
        "uk",
        "eu",
        "un",
    }
)


_STORM_NAME = re.compile(
    r"\b(?:hurricane|typhoon|cyclone|tropical storm|storm)\s+([A-Z][a-z]+)\b", re.IGNORECASE
)
_STORM_LEAD_CHARACTERS = 400
# Capitalised words that follow "Hurricane"/"Storm" without naming a storm.
_NOT_STORM_NAMES = frozenset(
    {"center", "centre", "season", "warning", "watch", "category", "prediction", "hunters", "the"}
)


def storm_names(title: str, content: str) -> frozenset[str]:
    """Named storms in the headline and lead: "Hurricane Simon" -> {"simon"}."""
    text = f"{title}. {clean_text(content)[:_STORM_LEAD_CHARACTERS]}"
    return frozenset(
        name.lower()
        for name in (match.group(1) for match in _STORM_NAME.finditer(text))
        if name[0].isupper() and name.lower() not in _NOT_STORM_NAMES
    )


def _distinctive_entities(
    shared: list[str], common: frozenset[str] = frozenset()
) -> list[str]:
    return [name for name in shared if name not in _GENERIC_ENTITIES and name not in common]


def common_entities(entity_sets: list[set[str]]) -> frozenset[str]:
    """Names too widespread in this dataset to identify one story.

    In a multi-month archive a name like "trump" or "gaza" can appear in
    hundreds of unrelated stories, so sharing only that name must not link
    two articles (it chained hurricanes and ceasefires into unrelated
    events). The bar is an absolute article count, so small inputs behave
    exactly as before.
    """
    limit = max(_COMMON_ENTITY_MIN_DOCS, len(entity_sets) // 100)
    counts: dict[str, int] = {}
    for names in entity_sets:
        for name in names:
            counts[name] = counts.get(name, 0) + 1
    return frozenset(name for name, seen in counts.items() if seen > limit)


def articles_describe_same_event(
    *,
    score: float,
    shared_entities: list[str],
    title_overlap: float,
    text_similarity: float,
    config: GroupingConfig = GROUPING,
    common_entities_set: frozenset[str] = frozenset(),
) -> bool:
    """True when two articles should join the same event."""
    if score < config.link_threshold:
        return False
    if title_overlap >= config.title_link_floor or text_similarity >= config.text_link_floor:
        return True
    distinctive = _distinctive_entities(shared_entities, common_entities_set)
    return len(distinctive) >= config.min_shared_entities


@dataclass(frozen=True)
class ArticleForGrouping:
    id: int
    title: str
    content: str
    published_at: datetime | None = None
    source_id: int | None = None


@dataclass(frozen=True)
class PairScore:
    left_id: int
    right_id: int
    text_similarity: float
    entity_overlap: float
    title_overlap: float
    hours_apart: float | None
    score: float
    linked: bool
    shared_entities: list[str] = field(default_factory=list)

    def explanation(self) -> str:
        parts = [
            f"text {self.text_similarity:.2f}",
            f"entities {self.entity_overlap:.2f}",
            f"titles {self.title_overlap:.2f}",
        ]
        if self.hours_apart is not None:
            parts.append(f"{self.hours_apart:.0f}h apart")
        return ", ".join(parts)


@dataclass
class EventCluster:
    article_ids: list[int]
    title: str
    event_time: datetime | None
    keywords: list[str]
    mean_link_score: float


def _time_factor(hours: float | None, config: GroupingConfig) -> float:
    """1.0 for simultaneous publication, `min_time_factor` at the window edge."""
    if hours is None:
        # Unknown publication time must not silently create or block a link.
        return 0.75
    if hours >= config.max_hours_apart:
        return 0.0
    closeness = 1.0 - (hours / config.max_hours_apart)
    return config.min_time_factor + (1.0 - config.min_time_factor) * closeness


def score_pairs(
    articles: list[ArticleForGrouping],
    config: GroupingConfig = GROUPING,
    keep_unlinked: bool = True,
) -> list[PairScore]:
    """Score article pairs. Pure function, used directly by the tests.

    Pairs published further apart than ``max_hours_apart`` can never link
    (their time factor is 0.0, so the score is 0.0 below any threshold).
    With ``keep_unlinked=False`` those dead pairs are skipped up front, which
    keeps grouping linear-ish in dataset size: a six-month archive only ever
    compares articles a few days apart. Undated articles are always compared.
    """
    if len(articles) < 2:
        return []

    documents = [
        f"{normalize_title(article.title)}. {clean_text(article.content)[:LEAD_CHARACTERS]}"
        for article in articles
    ]
    matrix, _ = build_tfidf_matrix(documents)
    similarities = cosine_matrix(matrix)
    entities = [entity_set(f"{article.title}. {article.content}") for article in articles]
    title_tokens = [token_set(normalize_title(article.title)) for article in articles]
    storms = [storm_names(article.title, article.content) for article in articles]
    widespread = common_entities(entities)
    max_gap_seconds = config.max_hours_apart * 3600.0
    epochs = [
        (as_utc(article.published_at).timestamp() if as_utc(article.published_at) else None)
        for article in articles
    ]

    scores: list[PairScore] = []
    for i in range(len(articles)):
        for j in range(i + 1, len(articles)):
            first, second = articles[i], articles[j]
            gap: float | None = None
            if epochs[i] is not None and epochs[j] is not None:
                gap = abs(epochs[j] - epochs[i])
            if gap is not None and gap >= max_gap_seconds:
                if not keep_unlinked:
                    continue
                scores.append(
                    PairScore(
                        left_id=first.id,
                        right_id=second.id,
                        text_similarity=0.0,
                        entity_overlap=0.0,
                        title_overlap=0.0,
                        hours_apart=gap / 3600.0,
                        score=0.0,
                        linked=False,
                    )
                )
                continue
            text_similarity = float(similarities[i][j]) if similarities.size else 0.0
            shared = sorted(entities[i] & entities[j])
            entity_overlap = jaccard(entities[i], entities[j])
            title_overlap = jaccard(title_tokens[i], title_tokens[j])
            hours = hours_between(first.published_at, second.published_at)
            factor = _time_factor(hours, config)
            raw = (
                config.text_weight * text_similarity
                + config.entity_weight * entity_overlap
                + config.title_weight * title_overlap
            )
            score = raw * factor
            linked = articles_describe_same_event(
                score=score,
                shared_entities=shared,
                title_overlap=title_overlap,
                text_similarity=text_similarity,
                config=config,
                common_entities_set=widespread,
            )
            if storms[i] and storms[j] and storms[i] != storms[j]:
                # Two different named storms are two events, even in the same week.
                linked = False
            scores.append(
                PairScore(
                    left_id=first.id,
                    right_id=second.id,
                    text_similarity=text_similarity,
                    entity_overlap=entity_overlap,
                    title_overlap=title_overlap,
                    hours_apart=hours,
                    score=score,
                    linked=linked,
                    shared_entities=shared[:8],
                )
            )
    return scores


class _UnionFind:
    def __init__(self, items: list[int]) -> None:
        self._parent = {item: item for item in items}

    def find(self, item: int) -> int:
        while self._parent[item] != item:
            self._parent[item] = self._parent[self._parent[item]]
            item = self._parent[item]
        return item

    def union(self, left: int, right: int) -> None:
        left_root, right_root = self.find(left), self.find(right)
        if left_root != right_root:
            self._parent[right_root] = left_root


def group_articles(
    articles: list[ArticleForGrouping], config: GroupingConfig = GROUPING
) -> list[EventCluster]:
    """Group articles into events. Single articles form single-article events."""
    if not articles:
        return []

    ordered = sorted(articles, key=lambda article: (as_utc(article.published_at) or _MIN_TIME, article.id))
    # Clustering only follows linked pairs; far-apart pairs can never link,
    # so they are pruned before scoring (see score_pairs).
    pairs = score_pairs(ordered, config, keep_unlinked=False)
    union_find = _UnionFind([article.id for article in ordered])
    link_scores: dict[int, list[float]] = {article.id: [] for article in ordered}
    for pair in pairs:
        if pair.linked:
            union_find.union(pair.left_id, pair.right_id)
            link_scores[pair.left_id].append(pair.score)
            link_scores[pair.right_id].append(pair.score)

    by_id = {article.id: article for article in ordered}
    members: dict[int, list[int]] = {}
    for article in ordered:
        members.setdefault(union_find.find(article.id), []).append(article.id)

    documents = [
        f"{normalize_title(by_id[article_id].title)}. {clean_text(by_id[article_id].content)[:LEAD_CHARACTERS]}"
        for article_id in [article.id for article in ordered]
    ]
    index_of = {article.id: index for index, article in enumerate(ordered)}
    matrix, vectorizer = build_tfidf_matrix(documents)
    similarities = cosine_matrix(matrix)

    clusters: list[EventCluster] = []
    for member_ids in members.values():
        member_ids.sort(key=lambda article_id: (as_utc(by_id[article_id].published_at) or _MIN_TIME, article_id))
        rows = [index_of[article_id] for article_id in member_ids]
        central_id = _most_central(member_ids, rows, similarities)
        times = [as_utc(by_id[article_id].published_at) for article_id in member_ids]
        known_times = [time for time in times if time is not None]
        collected = [score for article_id in member_ids for score in link_scores[article_id]]
        clusters.append(
            EventCluster(
                article_ids=member_ids,
                title=normalize_title(by_id[central_id].title),
                event_time=min(known_times) if known_times else None,
                keywords=top_terms(matrix, vectorizer, rows, limit=8),
                mean_link_score=round(sum(collected) / len(collected), 4) if collected else 0.0,
            )
        )

    clusters.sort(key=lambda cluster: (-len(cluster.article_ids), cluster.title))
    return clusters


def _most_central(member_ids: list[int], rows: list[int], similarities) -> int:
    """The article most similar to the rest of the group represents it."""
    if len(member_ids) == 1 or similarities.size == 0:
        return member_ids[0]
    best_id, best_total = member_ids[0], -1.0
    for article_id, row in zip(member_ids, rows, strict=True):
        total = float(sum(similarities[row][other] for other in rows if other != row))
        if total > best_total:
            best_id, best_total = article_id, total
    return best_id


_MIN_TIME = as_utc(datetime(1970, 1, 1))

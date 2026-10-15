"""Development identification.

An event is expressed as a chronological set of developments. Candidate
sentences that describe something happening are clustered by TF-IDF cosine
similarity; a cluster only becomes a development when enough distinct sources
report it. Live RSS items are mostly headlines, which often do not cluster
across outlets. If clustering yields nothing but the articles were already
grouped as one event, keep a single event-level development so coverage,
numbers and wording still have something to attach to.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime

from app.analysis.lexicons import ACTION_VERBS
from app.analysis.textutils import (
    build_tfidf_matrix,
    clean_text,
    content_tokens,
    cosine_matrix,
    normalize_title,
    split_sentences,
    top_terms,
    truncate_words,
)
from app.analysis.thresholds import DEVELOPMENTS, DevelopmentConfig
from app.core.timeutil import as_utc

_HAS_DIGIT = re.compile(r"\d")


@dataclass(frozen=True)
class ArticleForAnalysis:
    id: int
    source_id: int
    title: str
    content: str
    published_at: datetime | None = None
    source_name: str = ""


@dataclass(frozen=True)
class SupportingSentence:
    article_id: int
    source_id: int
    text: str
    published_at: datetime | None


@dataclass
class DevelopmentCandidate:
    title: str
    description: str
    occurred_at: datetime | None
    importance: float
    keywords: list[str]
    supporting_article_ids: list[int] = field(default_factory=list)
    supporting_source_ids: list[int] = field(default_factory=list)
    sentences: list[SupportingSentence] = field(default_factory=list)


def candidate_sentences(
    article: ArticleForAnalysis, config: DevelopmentConfig = DEVELOPMENTS
) -> list[str]:
    """Sentences that plausibly describe something that happened.

    Headlines are allowed to be shorter than body sentences: RSS items often
    have little besides the title, and that title is the outlet's statement of
    what happened.
    """
    title = normalize_title(article.title)
    selected: list[str] = []
    seen: set[str] = set()

    def consider(sentence: str, *, min_chars: int, min_tokens: int) -> None:
        if not (min_chars <= len(sentence) <= config.max_sentence_chars):
            return
        tokens = content_tokens(sentence)
        if len(tokens) < min_tokens:
            return
        has_action = any(token in ACTION_VERBS for token in tokens)
        if not has_action and not _HAS_DIGIT.search(sentence):
            return
        key = sentence.lower().rstrip(". ")
        if key in seen:
            return
        seen.add(key)
        selected.append(sentence)

    if title:
        consider(title, min_chars=20, min_tokens=3)
    body = f"{title}. {clean_text(article.content)}" if title else clean_text(article.content)
    for sentence in split_sentences(body):
        consider(sentence, min_chars=config.min_sentence_chars, min_tokens=4)
    return selected


def action_verbs_in(text: str) -> set[str]:
    return {token for token in content_tokens(text) if token in ACTION_VERBS}


def _actions_compatible(left: set[str], right: set[str]) -> bool:
    """Two sentences may describe the same development only if their actions
    agree. Without this, "closed the road" and "reopened the road" merge into a
    single development because they share almost every other word.
    """
    if not left or not right:
        return True
    return bool(left & right)


def _cluster_indices(similarities, threshold: float, actions: list[set[str]]) -> list[list[int]]:
    """Greedy single-link clustering in a stable, chronological order."""
    total = similarities.shape[0] if similarities.size else 0
    clusters: list[list[int]] = []
    for index in range(total):
        best_cluster, best_similarity = None, threshold
        for cluster in clusters:
            if not all(_actions_compatible(actions[index], actions[member]) for member in cluster):
                continue
            similarity = max(float(similarities[index][member]) for member in cluster)
            if similarity >= best_similarity:
                best_cluster, best_similarity = cluster, similarity
        if best_cluster is None:
            clusters.append([index])
        else:
            best_cluster.append(index)
    return clusters


def identify_developments(
    articles: list[ArticleForAnalysis], config: DevelopmentConfig = DEVELOPMENTS
) -> list[DevelopmentCandidate]:
    """Build the chronological developments of one event."""
    if not articles:
        return []

    ordered = sorted(articles, key=lambda a: (as_utc(a.published_at) or _MIN_TIME, a.id))
    sentences: list[SupportingSentence] = []
    for article in ordered:
        for sentence in candidate_sentences(article, config):
            sentences.append(
                SupportingSentence(
                    article_id=article.id,
                    source_id=article.source_id,
                    text=sentence,
                    published_at=as_utc(article.published_at),
                )
            )
    if not sentences:
        sentences = _headline_sentences(ordered)
    if not sentences:
        return []

    matrix, vectorizer = build_tfidf_matrix([sentence.text for sentence in sentences])
    similarities = cosine_matrix(matrix)
    if similarities.size == 0:
        return []

    distinct_sources = {article.source_id for article in articles}
    required_sources = min(config.min_supporting_sources, len(distinct_sources))
    actions = [action_verbs_in(sentence.text) for sentence in sentences]

    candidates: list[DevelopmentCandidate] = []
    for indices in _cluster_indices(similarities, config.cluster_threshold, actions):
        members = [sentences[index] for index in indices]
        source_ids = sorted({member.source_id for member in members})
        article_ids = sorted({member.article_id for member in members})
        if len(source_ids) < required_sources:
            continue
        representative = _representative_sentence(indices, members, similarities)
        times = [member.published_at for member in members if member.published_at]
        candidates.append(
            DevelopmentCandidate(
                title=truncate_words(representative, 26),
                description=representative,
                occurred_at=min(times) if times else None,
                importance=_importance(len(source_ids), len(distinct_sources), len(article_ids)),
                keywords=top_terms(matrix, vectorizer, indices, config.keywords_per_development),
                supporting_article_ids=article_ids,
                supporting_source_ids=source_ids,
                sentences=members,
            )
        )

    if not candidates:
        fallback = _event_level_development(
            sentences,
            similarities,
            matrix,
            vectorizer,
            required_sources,
            config,
        )
        return [fallback] if fallback is not None else []

    candidates.sort(key=lambda candidate: -candidate.importance)
    kept = candidates[: config.max_developments]
    kept.sort(key=lambda candidate: (candidate.occurred_at or _MIN_TIME, -candidate.importance))
    return kept


def _headline_sentences(articles: list[ArticleForAnalysis]) -> list[SupportingSentence]:
    """Last resort when no candidate sentence survived the filters."""
    sentences: list[SupportingSentence] = []
    for article in articles:
        title = normalize_title(article.title)
        if not title or len(content_tokens(title)) < 3:
            continue
        sentences.append(
            SupportingSentence(
                article_id=article.id,
                source_id=article.source_id,
                text=title,
                published_at=as_utc(article.published_at),
            )
        )
    return sentences


def _event_level_development(
    sentences: list[SupportingSentence],
    similarities,
    matrix,
    vectorizer,
    required_sources: int,
    config: DevelopmentConfig,
) -> DevelopmentCandidate | None:
    """One development from every candidate sentence of an already-grouped event.

    Sentence clustering often fails on short RSS blurbs even when the articles
    describe the same development. The fallback still requires as many distinct
    sources as clustering would have required.
    """
    source_ids = sorted({sentence.source_id for sentence in sentences})
    if len(source_ids) < required_sources:
        return None
    article_ids = sorted({sentence.article_id for sentence in sentences})
    indices = list(range(len(sentences)))
    representative = _representative_sentence(indices, sentences, similarities)
    times = [sentence.published_at for sentence in sentences if sentence.published_at]
    return DevelopmentCandidate(
        title=truncate_words(representative, 26),
        description=representative,
        occurred_at=min(times) if times else None,
        importance=_importance(len(source_ids), len(source_ids), len(article_ids)),
        keywords=top_terms(matrix, vectorizer, indices, config.keywords_per_development),
        supporting_article_ids=article_ids,
        supporting_source_ids=source_ids,
        sentences=sentences,
    )


def _representative_sentence(
    indices: list[int], members: list[SupportingSentence], similarities
) -> str:
    """The sentence closest to the rest of its cluster speaks for the cluster."""
    if len(indices) == 1:
        return members[0].text
    best_text, best_total = members[0].text, -1.0
    for position, index in enumerate(indices):
        total = float(sum(similarities[index][other] for other in indices if other != index))
        # Prefer the most central sentence; break ties towards the shorter one.
        if total > best_total or (total == best_total and len(members[position].text) < len(best_text)):
            best_text, best_total = members[position].text, total
    return best_text


def _importance(source_count: int, total_sources: int, article_count: int) -> float:
    """0..1 score driven by how widely a development is reported."""
    source_share = source_count / total_sources if total_sources else 0.0
    volume = min(article_count / 5.0, 1.0)
    return round(0.7 * source_share + 0.3 * volume, 4)


_MIN_TIME = as_utc(datetime(1970, 1, 1))

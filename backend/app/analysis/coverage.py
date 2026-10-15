"""Coverage analysis.

For every development and every article of an event, decide whether the article
reports that development. Evidence comes from sentence-level TF-IDF cosine
similarity plus keyword/entity overlap. Insufficient evidence produces
"unclear" rather than a forced yes or no.

Coverage is time-aware: an article published before a development happened is
marked not applicable and is left out of the coverage rate, so an outlet is
never penalised for a development it could not have reported yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from app.analysis.textutils import (
    build_tfidf_matrix,
    clean_text,
    cosine_similarity_rows,
    normalize_title,
    overlap_ratio,
    split_sentences,
    token_set,
)
from app.analysis.thresholds import COVERAGE, CoverageConfig
from app.core.timeutil import as_utc
from app.models.enums import CoverageStatus


@dataclass(frozen=True)
class DevelopmentForCoverage:
    id: int
    text: str
    keywords: list[str] = field(default_factory=list)
    occurred_at: datetime | None = None


@dataclass(frozen=True)
class ArticleForCoverage:
    id: int
    source_id: int
    title: str
    content: str
    published_at: datetime | None = None


@dataclass(frozen=True)
class CoverageDecision:
    development_id: int
    article_id: int
    source_id: int
    status: CoverageStatus
    similarity: float
    matched_terms: list[str]

    @property
    def is_applicable(self) -> bool:
        return self.status is not CoverageStatus.NOT_APPLICABLE


def _keyword_terms(development: DevelopmentForCoverage) -> set[str]:
    """Single words drawn from the development keywords and its own text."""
    terms: set[str] = set()
    for keyword in development.keywords:
        terms.update(token for token in keyword.split() if len(token) > 2)
    if not terms:
        terms = token_set(development.text)
    return terms


def assess_coverage(
    developments: list[DevelopmentForCoverage],
    articles: list[ArticleForCoverage],
    config: CoverageConfig = COVERAGE,
) -> list[CoverageDecision]:
    """Decide coverage for every development/article pair."""
    if not developments or not articles:
        return []

    article_sentences: dict[int, list[str]] = {}
    documents: list[str] = [development.text for development in developments]
    sentence_rows: dict[int, list[int]] = {}
    for article in articles:
        text = f"{normalize_title(article.title)}. {clean_text(article.content)}"
        sentences = [sentence for sentence in split_sentences(text) if len(sentence) > 20]
        article_sentences[article.id] = sentences
        sentence_rows[article.id] = list(
            range(len(documents), len(documents) + len(sentences))
        )
        documents.extend(sentences)

    matrix, _ = build_tfidf_matrix(documents)
    article_tokens = {
        article.id: token_set(f"{article.title}. {article.content}") for article in articles
    }

    decisions: list[CoverageDecision] = []
    for development_index, development in enumerate(developments):
        keywords = _keyword_terms(development)
        for article in articles:
            rows = sentence_rows[article.id]
            best_similarity = (
                cosine_similarity_rows(matrix, development_index, rows) if rows else 0.0
            )
            matched = sorted(keywords & article_tokens[article.id])
            keyword_score = overlap_ratio(keywords, article_tokens[article.id])
            score = round(
                config.sentence_weight * best_similarity + config.keyword_weight * keyword_score,
                4,
            )
            status = _status_for(score, config)
            if _published_before(development, article, config):
                status = CoverageStatus.NOT_APPLICABLE
            decisions.append(
                CoverageDecision(
                    development_id=development.id,
                    article_id=article.id,
                    source_id=article.source_id,
                    status=status,
                    similarity=score,
                    matched_terms=matched[:10],
                )
            )
    return decisions


def _status_for(score: float, config: CoverageConfig) -> CoverageStatus:
    if score >= config.covered_threshold:
        return CoverageStatus.COVERED
    if score >= config.unclear_threshold:
        return CoverageStatus.UNCLEAR
    return CoverageStatus.NOT_COVERED


def _published_before(
    development: DevelopmentForCoverage,
    article: ArticleForCoverage,
    config: CoverageConfig,
) -> bool:
    occurred_at = as_utc(development.occurred_at)
    published_at = as_utc(article.published_at)
    if occurred_at is None or published_at is None:
        return False
    return published_at < occurred_at - timedelta(hours=config.timing_grace_hours)


def coverage_rate(decisions: list[CoverageDecision]) -> float | None:
    """covered / relevant developments. None when nothing is applicable."""
    applicable = [decision for decision in decisions if decision.is_applicable]
    if not applicable:
        return None
    covered = sum(1 for decision in applicable if decision.status is CoverageStatus.COVERED)
    return round(covered / len(applicable), 4)


def coverage_rate_by_source(decisions: list[CoverageDecision]) -> dict[int, float | None]:
    grouped: dict[int, list[CoverageDecision]] = {}
    for decision in decisions:
        grouped.setdefault(decision.source_id, []).append(decision)
    return {source_id: coverage_rate(items) for source_id, items in grouped.items()}


def summarize_development(decisions: list[CoverageDecision]) -> dict[str, int]:
    counts = {status.value: 0 for status in CoverageStatus}
    for decision in decisions:
        counts[decision.status.value] += 1
    return counts

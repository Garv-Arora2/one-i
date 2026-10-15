"""Analysis orchestration.

Runs the full chain for a dataset and stores the results:
group articles into events -> developments -> coverage -> numbers -> wording
-> crux. This runs as a background/CLI job, never during a page request.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass, field, replace

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.analysis import crux as crux_module
from app.analysis.coverage import ArticleForCoverage, DevelopmentForCoverage, assess_coverage
from app.analysis.developments import ArticleForAnalysis, identify_developments
from app.analysis.entities import detect_locations
from app.analysis.grouping import ArticleForGrouping, group_articles
from app.analysis.numbers import build_comparisons, extract_numbers, observations_about_the_event
from app.analysis.textutils import TOPIC_SEPARATOR, slugify, strip_topic_breadcrumb
from app.analysis.thresholds import PUBLICATION
from app.analysis.wording import compare_wording, select_passages
from app.core.timeutil import as_utc
from app.db.base import utcnow
from app.models import (
    Article,
    Coverage,
    Development,
    Event,
    NumberObservation,
    Source,
    WordingObservation,
)

logger = logging.getLogger(__name__)


@dataclass
class AnalysisReport:
    events: int = 0
    developments: int = 0
    coverage_rows: int = 0
    number_observations: int = 0
    wording_observations: int = 0
    skipped_events: list[str] = field(default_factory=list)


def rebuild_dataset(session: Session, *, is_demo: bool) -> AnalysisReport:
    """Regroup and re-analyse every article in one dataset (demo or live)."""
    articles = list(
        session.scalars(select(Article).where(Article.is_demo == is_demo).order_by(Article.id))
    )
    report = AnalysisReport()
    if not articles:
        return report

    clusters = group_articles(
        [
            ArticleForGrouping(
                id=article.id,
                title=article.title,
                content=article.content,
                published_at=article.published_at,
                source_id=article.source_id,
            )
            for article in articles
        ]
    )

    by_id = {article.id: article for article in articles}
    used_event_ids: set[int] = set()
    used_slugs: set[str] = set()

    for article in articles:
        article.event_id = None
        article.grouping_score = None
    session.flush()

    for cluster in clusters:
        source_ids = {
            by_id[article_id].source_id
            for article_id in cluster.article_ids
            if by_id[article_id].source_id is not None
        }
        if len(source_ids) < PUBLICATION.min_sources:
            continue
        slug = _unique_slug(session, slugify(cluster.title), used_slugs)
        used_slugs.add(slug)
        event = session.scalar(
            select(Event).where(Event.slug == slug, Event.is_demo == is_demo)
        )
        if event is None:
            event = Event(slug=slug, title=cluster.title, is_demo=is_demo)
            session.add(event)
            session.flush()
        else:
            event.title = cluster.title
        used_event_ids.add(event.id)

        for article_id in cluster.article_ids:
            article = by_id[article_id]
            article.event_id = event.id
            article.grouping_score = cluster.mean_link_score
        session.flush()
        analyze_event(session, event, report)
        if not is_demo and not _meets_publication_threshold(session, event):
            # Grouped, but too thinly reported to power the product: withhold
            # the event while keeping the articles, so a later ingest with
            # fuller reporting can corroborate and publish it.
            _unpublish_event(session, event, by_id, cluster.article_ids)
            used_event_ids.discard(event.id)
            report.skipped_events.append(f"{slug} (below publication threshold)")
            continue
        report.events += 1

    _remove_empty_events(session, is_demo, used_event_ids)
    session.flush()
    return report


def _meets_publication_threshold(session: Session, event: Event) -> bool:
    """True when a live event has enough shared reporting to power ONE I."""
    development_count = session.scalar(
        select(func.count())
        .select_from(Development)
        .where(Development.event_id == event.id)
    ) or 0
    return development_count >= PUBLICATION.min_developments_for_live


def _unpublish_event(
    session: Session,
    event: Event,
    by_id: dict[int, Article],
    article_ids: list[int],
) -> None:
    """Remove a withheld event's rows but keep its articles for later."""
    _clear_previous_results(session, event.id)
    for article_id in article_ids:
        article = by_id.get(article_id)
        if article is not None:
            article.event_id = None
            article.grouping_score = None
    session.flush()
    session.delete(event)
    session.flush()


def _unique_slug(session: Session, base: str, used: set[str]) -> str:
    slug, suffix = base, 2
    while slug in used:
        slug = f"{base}-{suffix}"
        suffix += 1
    _ = session
    return slug


def _remove_empty_events(session: Session, is_demo: bool, keep: set[int]) -> None:
    stale = session.scalars(
        select(Event).where(Event.is_demo == is_demo, Event.id.notin_(keep or {0}))
    ).all()
    for event in stale:
        if not session.scalars(select(Article).where(Article.event_id == event.id)).first():
            session.delete(event)


def analyze_event(session: Session, event: Event, report: AnalysisReport | None = None) -> None:
    """Rebuild every stored analysis result for one event."""
    report = report or AnalysisReport()
    articles = list(
        session.scalars(
            select(Article).where(Article.event_id == event.id).order_by(Article.published_at, Article.id)
        )
    )
    if not articles:
        report.skipped_events.append(event.slug)
        return

    source_names = {
        source.id: source.name
        for source in session.scalars(
            select(Source).where(Source.id.in_({article.source_id for article in articles}))
        )
    }

    _clear_previous_results(session, event.id)

    analysis_articles = [
        ArticleForAnalysis(
            id=article.id,
            source_id=article.source_id,
            title=article.title,
            content=strip_topic_breadcrumb(article.content),
            published_at=article.published_at,
            source_name=source_names.get(article.source_id, ""),
        )
        for article in articles
    ]

    quotable_articles = _outlet_worded(articles, analysis_articles)

    development_rows = _store_developments(session, event, analysis_articles, report)
    _store_coverage(session, development_rows, analysis_articles, report)
    comparisons = _store_numbers(session, event, quotable_articles, development_rows, report)
    _store_wording(session, event, development_rows, quotable_articles, report)
    _store_crux(session, event, development_rows, comparisons, analysis_articles, source_names)

    event.last_analyzed_at = utcnow()
    session.flush()


def is_summary_only(article: Article) -> bool:
    """True when the stored text is Wikipedia's summary, not the outlet's page.

    Current-events rows start as "Topic › … — Wikipedia's one-line summary"
    and only become the outlet's words once its page has been fetched.
    """
    if article.ingest_provider != "currentevents":
        return False
    content = article.content or ""
    return TOPIC_SEPARATOR in content[:300] or content.strip() == (article.title or "").strip()


def _outlet_worded(
    articles: list[Article], analysis_articles: list[ArticleForAnalysis]
) -> list[ArticleForAnalysis]:
    """Articles whose text may be quoted and compared as the outlet's own words.

    Summary-only rows still count for grouping, timeline and coverage (the
    outlet was cited as reporting the event), but their sentences were
    written by Wikipedia editors, so numbers and wording never quote them.
    For fetched current-events rows the title is still Wikipedia's summary,
    so only the page text is used.
    """
    by_id = {article.id: article for article in articles}
    quotable: list[ArticleForAnalysis] = []
    for item in analysis_articles:
        article = by_id[item.id]
        if is_summary_only(article):
            continue
        if article.ingest_provider == "currentevents":
            item = replace(item, title="")
        quotable.append(item)
    return quotable


def _clear_previous_results(session: Session, event_id: int) -> None:
    development_ids = list(
        session.scalars(select(Development.id).where(Development.event_id == event_id))
    )
    if development_ids:
        session.execute(delete(Coverage).where(Coverage.development_id.in_(development_ids)))
    session.execute(delete(Development).where(Development.event_id == event_id))
    session.execute(delete(NumberObservation).where(NumberObservation.event_id == event_id))
    session.execute(delete(WordingObservation).where(WordingObservation.event_id == event_id))
    session.flush()


def _store_developments(
    session: Session,
    event: Event,
    articles: list[ArticleForAnalysis],
    report: AnalysisReport,
) -> list[Development]:
    candidates = identify_developments(articles)
    rows: list[Development] = []
    for position, candidate in enumerate(candidates):
        row = Development(
            event_id=event.id,
            title=candidate.title,
            description=candidate.description,
            occurred_at=candidate.occurred_at,
            importance=candidate.importance,
            supporting_article_count=len(candidate.supporting_article_ids),
            supporting_source_count=len(candidate.supporting_source_ids),
            keywords=candidate.keywords,
            position=position,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    report.developments += len(rows)
    return rows


def _store_coverage(
    session: Session,
    developments: list[Development],
    articles: list[ArticleForAnalysis],
    report: AnalysisReport,
) -> None:
    if not developments:
        return
    decisions = assess_coverage(
        [
            DevelopmentForCoverage(
                id=development.id,
                text=development.description or development.title,
                keywords=list(development.keywords or []),
                occurred_at=development.occurred_at,
            )
            for development in developments
        ],
        [
            ArticleForCoverage(
                id=article.id,
                source_id=article.source_id,
                title=article.title,
                content=article.content,
                published_at=article.published_at,
            )
            for article in articles
        ],
    )
    for decision in decisions:
        session.add(
            Coverage(
                development_id=decision.development_id,
                article_id=decision.article_id,
                status=decision.status.value,
                similarity=decision.similarity,
                matched_terms=decision.matched_terms,
            )
        )
    session.flush()
    report.coverage_rows += len(decisions)


def _store_numbers(
    session: Session,
    event: Event,
    articles: list[ArticleForAnalysis],
    developments: list[Development],
    report: AnalysisReport,
):
    observations = []
    for article in articles:
        observations.extend(
            extract_numbers(article.id, article.source_id, article.title, article.content)
        )
    observations = observations_about_the_event(
        observations,
        [(article.source_id, f"{article.title}. {article.content}") for article in articles],
    )
    comparisons = build_comparisons(observations)

    keys_by_observation: dict[int, str] = {}
    for comparison in comparisons:
        for observation in comparison.observations:
            keys_by_observation[id(observation)] = comparison.comparison_key

    development_lookup = _development_lookup(developments)
    for observation in observations:
        session.add(
            NumberObservation(
                article_id=observation.article_id,
                event_id=event.id,
                development_id=development_lookup(observation.context),
                description=observation.subject,
                reported_value=observation.value,
                unit=observation.unit,
                value_kind=observation.value_kind.value,
                time_period=observation.time_period,
                context=observation.context,
                # Empty means "extracted but not comparable to anything";
                # only observations inside a kept comparison carry a key.
                comparison_key=keys_by_observation.get(id(observation), ""),
            )
        )
    session.flush()
    report.number_observations += len(observations)
    return comparisons


def _development_lookup(developments: list[Development]):
    """Attach an observation/passage to the development whose words it shares."""
    profiles = [
        (development.id, set((development.keywords or [])) | set((development.title or "").lower().split()))
        for development in developments
    ]

    def lookup(text: str) -> int | None:
        tokens = set(text.lower().split())
        best_id, best_score = None, 0
        for development_id, keywords in profiles:
            score = len({keyword for keyword in keywords if keyword in tokens})
            if score > best_score:
                best_id, best_score = development_id, score
        return best_id if best_score >= 2 else None

    return lookup


def _store_wording(
    session: Session,
    event: Event,
    developments: list[Development],
    articles: list[ArticleForAnalysis],
    report: AnalysisReport,
) -> None:
    stored = 0
    for development in developments:
        passages = select_passages(
            development.description or development.title,
            [
                (article.id, article.source_id, article.source_name, article.title, article.content)
                for article in articles
            ],
        )
        comparison = compare_wording(
            topic=development.title, passages=passages, development_id=development.id
        )
        if comparison is None:
            continue
        for passage in comparison.passages:
            session.add(
                WordingObservation(
                    article_id=passage.article_id,
                    event_id=event.id,
                    development_id=development.id,
                    topic=comparison.topic,
                    quoted_text=passage.text,
                    surrounding_text=passage.surrounding_text,
                    description=", ".join(comparison.differing_aspects) or None,
                    aspects=passage.aspects,
                    markers=passage.markers,
                )
            )
            stored += 1
    session.flush()
    report.wording_observations += stored


def _store_crux(
    session: Session,
    event: Event,
    developments: list[Development],
    comparisons,
    articles: list[ArticleForAnalysis],
    source_names: dict[int, str],
) -> None:
    published_times = [as_utc(article.published_at) for article in articles if article.published_at]
    event.event_time = min(published_times) if published_times else None

    location_counts: Counter[str] = Counter()
    for development in developments:
        for name in detect_locations(development.description or development.title):
            location_counts[name] += 1
    event.location = next(
        (name for name, count in location_counts.most_common(1) if count >= 2), None
    )

    result = crux_module.build_crux(
        title=event.title,
        event_time=event.event_time,
        location=event.location,
        developments=[
            crux_module.CruxDevelopment(
                id=development.id,
                title=development.title,
                description=development.description or development.title,
                occurred_at=development.occurred_at,
                importance=development.importance,
                supporting_article_ids=_supporting_articles(session, development.id),
            )
            for development in developments
        ],
        number_comparisons=comparisons,
        articles=[
            crux_module.CruxArticle(
                id=article.id,
                source_id=article.source_id,
                source_name=source_names.get(article.source_id, ""),
                published_at=article.published_at,
            )
            for article in articles
        ],
    )
    event.crux = result.text
    event.context = result.context_text
    event.crux_data = result.to_dict()
    _ = session


def _supporting_articles(session: Session, development_id: int) -> list[int]:
    return list(
        session.scalars(
            select(Coverage.article_id).where(
                Coverage.development_id == development_id, Coverage.status == "covered"
            )
        )
    )

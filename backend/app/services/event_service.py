"""Read services.

These functions only read stored rows and do cheap arithmetic over them. The
expensive text analysis happens in `analysis_service` before a user ever asks
for the page.
"""

from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis.crux import format_value
from app.analysis.market import PricePoint, compute_market_impact
from app.analysis.numbers import NumberObservationCandidate, compare_group
from app.analysis.reaction import ReactionItem, aggregate_reactions, event_terms
from app.analysis.textutils import short_title
from app.analysis.thresholds import PUBLICATION
from app.models import (
    Article,
    Coverage,
    Development,
    Event,
    MarketData,
    NumberObservation,
    PublicReaction,
    Source,
    WordingObservation,
)
from app.models.enums import CoverageStatus, ValueKind
from app.schemas.events import (
    ArticleRef,
    ComparisonsResponse,
    CoverageCell,
    CoverageResponse,
    CruxPartOut,
    DevelopmentOut,
    EventDetail,
    EventSummary,
    MarketPointOut,
    MarketResponse,
    NumberComparisonOut,
    NumberObservationOut,
    ReactionItemOut,
    ReactionsResponse,
    SourceCoverage,
    SourceRef,
    TimelineResponse,
    WordingComparisonOut,
    WordingPassageOut,
)
from app.schemas.sources import (
    SourceDetail,
    SourceEventCoverage,
    SourceOut,
)

_STATUS_PRIORITY = {
    CoverageStatus.COVERED.value: 0,
    CoverageStatus.UNCLEAR.value: 1,
    CoverageStatus.NOT_COVERED.value: 2,
    CoverageStatus.NOT_APPLICABLE.value: 3,
}


def _source_ref(source: Source) -> SourceRef:
    return SourceRef(
        id=source.id, name=source.name, domain=source.domain, source_type=source.source_type
    )


def _event_ordering(sort: str, coverage):
    """Front-page ordering. Unknown values fall back to most-covered-first."""
    if sort == "recent":
        return (Event.event_time.desc().nulls_last(), Event.id.desc())
    if sort == "oldest":
        return (
            Event.event_time.asc().nulls_first(),
            Event.id.asc(),
        )
    return (
        coverage.c.sources.desc(),
        coverage.c.articles.desc(),
        Event.event_time.desc().nulls_last(),
        Event.id.desc(),
    )


def get_event(session: Session, reference: str) -> Event | None:
    """Look an event up by numeric id or by slug."""
    if reference.isdigit():
        event = session.get(Event, int(reference))
        if event is not None:
            return event
    return session.scalar(select(Event).where(Event.slug == reference))


def _event_counts(session: Session, event_ids: list[int]) -> dict[int, dict[str, int]]:
    counts: dict[int, dict[str, int]] = {
        event_id: {
            "articles": 0,
            "sources": 0,
            "developments": 0,
            "market": 0,
            "reactions": 0,
        }
        for event_id in event_ids
    }
    if not event_ids:
        return counts

    for event_id, articles, sources in session.execute(
        select(Article.event_id, func.count(Article.id), func.count(func.distinct(Article.source_id)))
        .where(Article.event_id.in_(event_ids))
        .group_by(Article.event_id)
    ):
        counts[event_id]["articles"] = articles
        counts[event_id]["sources"] = sources
    for event_id, total in session.execute(
        select(Development.event_id, func.count(Development.id))
        .where(Development.event_id.in_(event_ids))
        .group_by(Development.event_id)
    ):
        counts[event_id]["developments"] = total
    for event_id, total in session.execute(
        select(MarketData.event_id, func.count(MarketData.id))
        .where(MarketData.event_id.in_(event_ids))
        .group_by(MarketData.event_id)
    ):
        counts[event_id]["market"] = total
    for event_id, total in session.execute(
        select(PublicReaction.event_id, func.count(PublicReaction.id))
        .where(PublicReaction.event_id.in_(event_ids))
        .group_by(PublicReaction.event_id)
    ):
        counts[event_id]["reactions"] = total
    return counts


def _lead_crux(event: Event) -> str | None:
    """The opening statement of the crux.

    ``Event.crux`` is every labelled part rendered into one block of prose,
    which is too long to read as a standfirst. The labelled parts are returned
    separately, so callers only need the first one here.
    """
    parts = (event.crux_data or {}).get("parts") or []
    if parts and parts[0].get("text"):
        return parts[0]["text"]
    return event.crux


def _summary(event: Event, counts: dict[str, int]) -> EventSummary:
    return EventSummary(
        id=event.id,
        slug=event.slug,
        title=event.title,
        crux=_lead_crux(event),
        event_time=event.event_time,
        location=event.location,
        is_demo=event.is_demo,
        article_count=counts["articles"],
        source_count=counts["sources"],
        development_count=counts["developments"],
        has_market_data=counts["market"] > 0,
        has_reactions=counts["reactions"] > 0,
    )


def list_events(
    session: Session,
    *,
    dataset: str = "all",
    limit: int = 20,
    offset: int = 0,
    min_sources: int | None = None,
    sort: str = "sources",
) -> tuple[list[EventSummary], int]:
    """Return events worth reading as comparisons.

    Live news is capped to a short front-page run (about three to four
    pages of well-covered events). Demo data is not capped. `sort` is one
    of "sources" (most covered first), "recent" (as it happened, newest
    first) or "oldest".
    """
    required_sources = PUBLICATION.min_sources if min_sources is None else min_sources
    coverage = (
        select(
            Article.event_id.label("event_id"),
            func.count(func.distinct(Article.source_id)).label("sources"),
            func.count(Article.id).label("articles"),
        )
        .where(Article.event_id.is_not(None))
        .group_by(Article.event_id)
        .having(func.count(func.distinct(Article.source_id)) >= required_sources)
        .subquery()
    )
    statement = select(Event).join(coverage, Event.id == coverage.c.event_id)
    if dataset == "demo":
        statement = statement.where(Event.is_demo.is_(True))
    elif dataset == "live":
        statement = statement.where(Event.is_demo.is_(False))
        # Belt and braces with the analysis-time threshold: a live event is
        # only listed when its reporting can power timeline and coverage.
        developed = (
            select(
                Development.event_id.label("event_id"),
                func.count(Development.id).label("developments"),
            )
            .group_by(Development.event_id)
            .having(
                func.count(Development.id) >= PUBLICATION.min_developments_for_live
            )
            .subquery()
        )
        statement = statement.join(developed, Event.id == developed.c.event_id)

    statement = statement.order_by(*_event_ordering(sort, coverage))

    keep = PUBLICATION.page_size * PUBLICATION.max_pages if dataset == "live" else None
    if keep is not None:
        ranked = list(session.scalars(statement.limit(keep)))
        total = len(ranked)
        events = ranked[offset : offset + limit]
    else:
        total = session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        events = list(session.scalars(statement.limit(limit).offset(offset)))

    counts = _event_counts(session, [event.id for event in events])
    return [_summary(event, counts[event.id]) for event in events], total


def build_event_detail(session: Session, event: Event) -> EventDetail:
    counts = _event_counts(session, [event.id])[event.id]
    articles = list(
        session.scalars(
            select(Article)
            .where(Article.event_id == event.id)
            .order_by(Article.published_at, Article.id)
        )
    )
    sources = _sources_by_id(session, {article.source_id for article in articles})
    crux_data = event.crux_data or {}
    return EventDetail(
        **_summary(event, counts).model_dump(),
        context=event.context,
        crux_parts=[CruxPartOut(**part) for part in crux_data.get("parts", [])],
        context_parts=[CruxPartOut(**part) for part in crux_data.get("context_parts", [])],
        last_analyzed_at=event.last_analyzed_at,
        articles=[
            ArticleRef(
                id=article.id,
                title=article.title,
                url=article.url,
                published_at=article.published_at,
                source=_source_ref(sources[article.source_id]),
                title_is_summary=article.ingest_provider == "currentevents",
            )
            for article in articles
        ],
    )


def _sources_by_id(session: Session, source_ids: set[int]) -> dict[int, Source]:
    if not source_ids:
        return {}
    return {
        source.id: source
        for source in session.scalars(select(Source).where(Source.id.in_(source_ids)))
    }


def _developments(session: Session, event_id: int) -> list[Development]:
    return list(
        session.scalars(
            select(Development)
            .where(Development.event_id == event_id)
            .order_by(Development.occurred_at, Development.position)
        )
    )


def _coverage_rows(session: Session, development_ids: list[int]) -> list[Coverage]:
    if not development_ids:
        return []
    return list(
        session.scalars(select(Coverage).where(Coverage.development_id.in_(development_ids)))
    )


def _development_out(
    development: Development, covered_sources: int
) -> DevelopmentOut:
    return DevelopmentOut(
        id=development.id,
        title=development.title,
        short_title=short_title(development.title),
        description=development.description,
        occurred_at=development.occurred_at,
        importance=development.importance,
        supporting_article_count=development.supporting_article_count,
        supporting_source_count=development.supporting_source_count,
        covered_by_source_count=covered_sources,
    )


def build_timeline(session: Session, event: Event) -> TimelineResponse:
    developments = _developments(session, event.id)
    rows = _coverage_rows(session, [development.id for development in developments])
    article_sources = _article_source_map(session, event.id)
    covered_sources: dict[int, set[int]] = defaultdict(set)
    for row in rows:
        if row.status == CoverageStatus.COVERED.value:
            covered_sources[row.development_id].add(article_sources.get(row.article_id, -1))

    return TimelineResponse(
        event_id=event.id,
        developments=[
            _development_out(development, len(covered_sources.get(development.id, set())))
            for development in developments
        ],
        note=None
        if developments
        else "No developments could be identified from the available reporting.",
    )


def _article_source_map(session: Session, event_id: int) -> dict[int, int]:
    return {
        article_id: source_id
        for article_id, source_id in session.execute(
            select(Article.id, Article.source_id).where(Article.event_id == event_id)
        )
    }


def build_coverage(session: Session, event: Event) -> CoverageResponse:
    developments = _developments(session, event.id)
    if not developments:
        return CoverageResponse(
            event_id=event.id,
            developments=[],
            sources=[],
            cells=[],
            overall_coverage_rate=None,
            note="No developments could be identified, so coverage cannot be compared yet.",
        )

    articles = {
        article.id: article
        for article in session.scalars(select(Article).where(Article.event_id == event.id))
    }
    sources = _sources_by_id(session, {article.source_id for article in articles.values()})
    rows = _coverage_rows(session, [development.id for development in developments])

    # One article per source per development would be ambiguous for a source
    # that published several updates, so the source keeps its strongest result.
    best: dict[tuple[int, int], Coverage] = {}
    for row in rows:
        article = articles.get(row.article_id)
        if article is None:
            continue
        key = (row.development_id, article.source_id)
        current = best.get(key)
        if current is None or _is_stronger(row, current):
            best[key] = row

    cells: list[CoverageCell] = []
    per_source: dict[int, dict[str, int]] = defaultdict(
        lambda: {status.value: 0 for status in CoverageStatus}
    )
    covered_sources: dict[int, set[int]] = defaultdict(set)
    for (development_id, source_id), row in sorted(best.items()):
        article = articles[row.article_id]
        cells.append(
            CoverageCell(
                development_id=development_id,
                source_id=source_id,
                status=row.status,
                similarity=row.similarity,
                matched_terms=list(row.matched_terms or []),
                article_id=article.id,
                article_url=article.url,
            )
        )
        per_source[source_id][row.status] += 1
        if row.status == CoverageStatus.COVERED.value:
            covered_sources[development_id].add(source_id)

    source_coverage: list[SourceCoverage] = []
    total_covered = total_applicable = 0
    for source_id, counts in per_source.items():
        applicable = (
            counts[CoverageStatus.COVERED.value]
            + counts[CoverageStatus.UNCLEAR.value]
            + counts[CoverageStatus.NOT_COVERED.value]
        )
        covered = counts[CoverageStatus.COVERED.value]
        total_covered += covered
        total_applicable += applicable
        source_coverage.append(
            SourceCoverage(
                source=_source_ref(sources[source_id]),
                coverage_rate=round(covered / applicable, 4) if applicable else None,
                covered=covered,
                unclear=counts[CoverageStatus.UNCLEAR.value],
                not_covered=counts[CoverageStatus.NOT_COVERED.value],
                not_applicable=counts[CoverageStatus.NOT_APPLICABLE.value],
            )
        )
    source_coverage.sort(key=lambda item: item.source.name)

    return CoverageResponse(
        event_id=event.id,
        developments=[
            _development_out(development, len(covered_sources.get(development.id, set())))
            for development in developments
        ],
        sources=source_coverage,
        cells=cells,
        overall_coverage_rate=round(total_covered / total_applicable, 4)
        if total_applicable
        else None,
    )


def _is_stronger(candidate: Coverage, current: Coverage) -> bool:
    candidate_rank = _STATUS_PRIORITY.get(candidate.status, 9)
    current_rank = _STATUS_PRIORITY.get(current.status, 9)
    if candidate_rank != current_rank:
        return candidate_rank < current_rank
    return candidate.similarity > current.similarity


def build_comparisons(session: Session, event: Event) -> ComparisonsResponse:
    articles = {
        article.id: article
        for article in session.scalars(select(Article).where(Article.event_id == event.id))
    }
    sources = _sources_by_id(session, {article.source_id for article in articles.values()})

    observations = list(
        session.scalars(
            select(NumberObservation).where(
                NumberObservation.event_id == event.id, NumberObservation.comparison_key != ""
            )
        )
    )
    grouped: dict[str, list[NumberObservation]] = defaultdict(list)
    for observation in observations:
        grouped[observation.comparison_key].append(observation)

    numbers: list[NumberComparisonOut] = []
    for group in grouped.values():
        article_ids = {row.article_id for row in group}
        if len({articles[row.article_id].source_id for row in group if row.article_id in articles}) < 2:
            continue
        comparison = compare_group(
            [
                NumberObservationCandidate(
                    article_id=row.article_id,
                    source_id=articles[row.article_id].source_id,
                    value=row.reported_value,
                    unit=row.unit,
                    value_kind=ValueKind(row.value_kind),
                    subject=row.description,
                    subject_tokens=tuple(sorted(row.description.split())),
                    time_period=row.time_period,
                    context=row.context,
                    coarse_key=row.comparison_key,
                )
                for row in group
                if row.article_id in articles
            ]
        )
        numbers.append(
            NumberComparisonOut(
                subject=comparison.subject,
                unit=comparison.unit,
                value_kind=comparison.value_kind.value,
                time_period=comparison.time_period,
                sources_agree=comparison.sources_agree,
                lowest=comparison.lowest,
                highest=comparison.highest,
                difference=comparison.difference,
                difference_unit=comparison.difference_unit,
                relative_difference_percent=comparison.relative_difference_percent,
                observations=[
                    NumberObservationOut(
                        article_id=item.article_id,
                        source=_source_ref(sources[articles[item.article_id].source_id]),
                        value=item.value,
                        formatted_value=format_value(item.value, item.value_kind, item.unit),
                        context=item.context,
                        article_url=articles[item.article_id].url,
                    )
                    for item in comparison.observations
                ],
            )
        )
        _ = article_ids
    numbers.sort(key=lambda item: (item.sources_agree, -len(item.observations)))

    wording_rows = list(
        session.scalars(
            select(WordingObservation)
            .where(WordingObservation.event_id == event.id)
            .order_by(WordingObservation.development_id, WordingObservation.id)
        )
    )
    wording_groups: dict[tuple[int | None, str], list[WordingObservation]] = defaultdict(list)
    for row in wording_rows:
        wording_groups[(row.development_id, row.topic)].append(row)

    wording: list[WordingComparisonOut] = []
    for (development_id, topic), rows in wording_groups.items():
        aspects = sorted({aspect for row in rows for aspect in (row.description or "").split(", ") if aspect})
        wording.append(
            WordingComparisonOut(
                topic=topic,
                development_id=development_id,
                differing_aspects=aspects,
                passages=[
                    WordingPassageOut(
                        article_id=row.article_id,
                        source=_source_ref(sources[articles[row.article_id].source_id]),
                        article_url=articles[row.article_id].url,
                        quoted_text=row.quoted_text,
                        surrounding_text=row.surrounding_text,
                        aspects=list(row.aspects or []),
                        markers=dict(row.markers or {}),
                    )
                    for row in rows
                    if row.article_id in articles
                ],
            )
        )

    note = None
    if not numbers and not wording:
        note = "No comparable numbers or wording differences were found across these sources."
    return ComparisonsResponse(event_id=event.id, numbers=numbers, wording=wording, note=note)


def build_reactions(session: Session, event: Event) -> ReactionsResponse:
    rows = list(
        session.scalars(select(PublicReaction).where(PublicReaction.event_id == event.id))
    )
    summary = aggregate_reactions(
        [
            ReactionItem(
                id=row.id,
                platform=row.platform,
                content=row.content,
                published_at=row.published_at,
                engagement=row.engagement,
                url=row.url,
                community=row.community,
            )
            for row in rows
        ],
        event_terms(event.title, event.crux or ""),
    )
    return ReactionsResponse(
        event_id=event.id,
        available=summary.available,
        unavailable_reason=summary.unavailable_reason,
        total=summary.total,
        by_platform=summary.by_platform,
        timeline=summary.timeline,
        highlights=[
            ReactionItemOut(
                platform=item.platform,
                content=item.content,
                published_at=item.published_at,
                engagement=item.engagement,
                url=item.url,
                community=item.community,
            )
            for item in summary.highlights
        ],
    )


def build_market(session: Session, event: Event) -> MarketResponse:
    rows = list(
        session.scalars(
            select(MarketData).where(MarketData.event_id == event.id).order_by(MarketData.timestamp)
        )
    )
    if not rows:
        return MarketResponse(
            event_id=event.id,
            available=False,
            unavailable_reason="This event has no connected security, so no market data is shown.",
        )

    security_rows = [row for row in rows if not row.is_benchmark]
    benchmark_rows = [row for row in rows if row.is_benchmark]
    if not security_rows:
        return MarketResponse(
            event_id=event.id,
            available=False,
            unavailable_reason="No security price series is available for this event.",
        )

    impact = compute_market_impact(
        symbol=security_rows[0].symbol,
        name=security_rows[0].name,
        security_points=[
            PricePoint(timestamp=row.timestamp, price=row.price, volume=row.volume)
            for row in security_rows
        ],
        event_time=event.event_time,
        benchmark_symbol=benchmark_rows[0].symbol if benchmark_rows else None,
        benchmark_points=[
            PricePoint(timestamp=row.timestamp, price=row.price, volume=row.volume)
            for row in benchmark_rows
        ]
        or None,
    )
    return MarketResponse(
        event_id=event.id,
        available=impact.available,
        unavailable_reason=impact.unavailable_reason,
        symbol=impact.symbol,
        name=impact.name,
        window_start=impact.window_start,
        window_end=impact.window_end,
        start_price=impact.start_price,
        end_price=impact.end_price,
        return_percent=impact.return_percent,
        benchmark_symbol=impact.benchmark_symbol,
        benchmark_return_percent=impact.benchmark_return_percent,
        difference_percentage_points=impact.difference_percentage_points,
        baseline_average_volume=impact.baseline_average_volume,
        window_average_volume=impact.window_average_volume,
        volume_change_percent=impact.volume_change_percent,
        series=[MarketPointOut(**point) for point in impact.series],
        benchmark_series=[MarketPointOut(**point) for point in impact.benchmark_series],
    )


def list_sources(session: Session) -> list[SourceOut]:
    sources = list(session.scalars(select(Source).order_by(Source.name)))
    counts = {
        source_id: (articles, events)
        for source_id, articles, events in session.execute(
            select(
                Article.source_id,
                func.count(Article.id),
                func.count(func.distinct(Article.event_id)),
            ).group_by(Article.source_id)
        )
    }
    return [
        SourceOut(
            id=source.id,
            name=source.name,
            domain=source.domain,
            source_type=source.source_type,
            is_demo=source.is_demo,
            article_count=counts.get(source.id, (0, 0))[0],
            event_count=counts.get(source.id, (0, 0))[1],
        )
        for source in sources
    ]


def build_source_detail(session: Session, source: Source) -> SourceDetail:
    articles = list(session.scalars(select(Article).where(Article.source_id == source.id)))
    event_ids = {article.event_id for article in articles if article.event_id}
    events = {
        event.id: event
        for event in session.scalars(select(Event).where(Event.id.in_(event_ids or {0})))
    }

    per_event: list[SourceEventCoverage] = []
    for event_id, event in sorted(
        events.items(), key=lambda item: (item[1].event_time is None, item[1].event_time), reverse=True
    ):
        coverage = build_coverage(session, event)
        entry = next(
            (item for item in coverage.sources if item.source.id == source.id), None
        )
        per_event.append(
            SourceEventCoverage(
                event_id=event_id,
                event_slug=event.slug,
                event_title=event.title,
                event_time=event.event_time,
                article_count=sum(
                    1 for article in articles if article.event_id == event_id
                ),
                coverage_rate=entry.coverage_rate if entry else None,
                covered=entry.covered if entry else 0,
                unclear=entry.unclear if entry else 0,
                not_covered=entry.not_covered if entry else 0,
                not_applicable=entry.not_applicable if entry else 0,
            )
        )

    return SourceDetail(
        id=source.id,
        name=source.name,
        domain=source.domain,
        source_type=source.source_type,
        is_demo=source.is_demo,
        article_count=len(articles),
        event_count=len(event_ids),
        events=per_event,
    )

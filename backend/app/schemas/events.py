"""Public API schemas.

Kept separate from the database models: the API contract is allowed to be
stable while the storage changes.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceRef(BaseModel):
    id: int
    name: str
    domain: str
    source_type: str


class ArticleRef(BaseModel):
    id: int
    title: str
    url: str
    published_at: datetime | None
    source: SourceRef
    # True when the title is Wikipedia's one-line summary of the outlet's
    # report (current-events citations), not the outlet's own headline.
    title_is_summary: bool = False


class CruxPartOut(BaseModel):
    label: str
    text: str
    article_ids: list[int] = Field(default_factory=list)


class EventSummary(BaseModel):
    id: int
    slug: str
    title: str
    crux: str | None
    event_time: datetime | None
    location: str | None
    is_demo: bool
    article_count: int
    source_count: int
    development_count: int
    has_market_data: bool
    has_reactions: bool
    image_url: str | None = None


class EventDetail(EventSummary):
    context: str | None
    crux_parts: list[CruxPartOut] = Field(default_factory=list)
    context_parts: list[CruxPartOut] = Field(default_factory=list)
    last_analyzed_at: datetime | None
    articles: list[ArticleRef] = Field(default_factory=list)


class EventListResponse(BaseModel):
    events: list[EventSummary]
    total: int


class DevelopmentOut(BaseModel):
    id: int
    title: str
    # One-line summary for comparison views (coverage grid, missed facts).
    # The full title is always kept alongside for detail views.
    short_title: str
    description: str | None
    occurred_at: datetime | None
    importance: float
    supporting_article_count: int
    supporting_source_count: int
    covered_by_source_count: int


class TimelineResponse(BaseModel):
    event_id: int
    developments: list[DevelopmentOut]
    note: str | None = None


class CoverageCell(BaseModel):
    development_id: int
    source_id: int
    status: str
    similarity: float
    matched_terms: list[str] = Field(default_factory=list)
    article_id: int | None = None
    article_url: str | None = None


class SourceCoverage(BaseModel):
    source: SourceRef
    coverage_rate: float | None
    covered: int
    unclear: int
    not_covered: int
    not_applicable: int


class CoverageResponse(BaseModel):
    event_id: int
    developments: list[DevelopmentOut]
    sources: list[SourceCoverage]
    cells: list[CoverageCell]
    overall_coverage_rate: float | None
    note: str | None = None


class NumberObservationOut(BaseModel):
    article_id: int
    source: SourceRef
    value: float
    formatted_value: str
    context: str
    article_url: str


class NumberComparisonOut(BaseModel):
    subject: str
    unit: str | None
    value_kind: str
    time_period: str | None
    sources_agree: bool
    lowest: float
    highest: float
    difference: float
    difference_unit: str
    relative_difference_percent: float | None
    observations: list[NumberObservationOut]


class WordingPassageOut(BaseModel):
    article_id: int
    source: SourceRef
    article_url: str
    quoted_text: str
    surrounding_text: str | None
    aspects: list[str] = Field(default_factory=list)
    markers: dict[str, list[str]] = Field(default_factory=dict)


class WordingComparisonOut(BaseModel):
    topic: str
    development_id: int | None
    differing_aspects: list[str]
    passages: list[WordingPassageOut]


class ComparisonsResponse(BaseModel):
    event_id: int
    numbers: list[NumberComparisonOut]
    wording: list[WordingComparisonOut]
    note: str | None = None


class ReactionItemOut(BaseModel):
    platform: str
    content: str
    published_at: datetime | None
    engagement: int
    url: str | None
    community: str | None


class ReactionsResponse(BaseModel):
    event_id: int
    available: bool
    unavailable_reason: str | None = None
    total: int = 0
    by_platform: dict[str, dict[str, int]] = Field(default_factory=dict)
    timeline: list[dict] = Field(default_factory=list)
    # The most-liked comments that are about the event.
    highlights: list[ReactionItemOut] = Field(default_factory=list)
    disclaimer: str = (
        "Public discussion is shown as context. It is not evidence that a claim is true."
    )


class MarketPointOut(BaseModel):
    timestamp: str
    price: float
    volume: float | None


class MarketResponse(BaseModel):
    event_id: int
    available: bool
    unavailable_reason: str | None = None
    symbol: str | None = None
    name: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    start_price: float | None = None
    end_price: float | None = None
    return_percent: float | None = None
    benchmark_symbol: str | None = None
    benchmark_return_percent: float | None = None
    difference_percentage_points: float | None = None
    baseline_average_volume: float | None = None
    window_average_volume: float | None = None
    volume_change_percent: float | None = None
    series: list[MarketPointOut] = Field(default_factory=list)
    benchmark_series: list[MarketPointOut] = Field(default_factory=list)
    disclaimer: str = (
        "Price movement observed during the selected window. "
        "This does not establish that the event caused the movement."
    )

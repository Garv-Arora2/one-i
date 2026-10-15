"""Source-facing API schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class SourceOut(BaseModel):
    id: int
    name: str
    domain: str
    source_type: str
    is_demo: bool
    article_count: int
    event_count: int


class SourceEventCoverage(BaseModel):
    event_id: int
    event_slug: str
    event_title: str
    event_time: datetime | None
    article_count: int
    coverage_rate: float | None
    covered: int
    unclear: int
    not_covered: int
    not_applicable: int


class SourceDetail(SourceOut):
    events: list[SourceEventCoverage] = Field(default_factory=list)


class SourceListResponse(BaseModel):
    sources: list[SourceOut]
    total: int

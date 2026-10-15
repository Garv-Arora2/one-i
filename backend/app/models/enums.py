"""Stable string values used by the schema and the API.

These are stored as plain strings so that adding a value never requires a
PostgreSQL enum migration.
"""

from __future__ import annotations

from enum import StrEnum


class CoverageStatus(StrEnum):
    COVERED = "covered"
    UNCLEAR = "unclear"
    NOT_COVERED = "not_covered"
    # The article was published before this development happened, so it could
    # not have reported it. Excluded from coverage rates (see docs/specs/coverage.md).
    NOT_APPLICABLE = "not_applicable"


class ValueKind(StrEnum):
    """How a reported number must be interpreted when compared."""

    PERCENT = "percent"
    PERCENTAGE_POINT = "percentage_point"
    PERCENT_CHANGE = "percent_change"
    CURRENCY = "currency"
    COUNT = "count"
    DURATION = "duration"
    OTHER = "other"


class WordingAspect(StrEnum):
    RESPONSIBILITY = "responsibility"
    ACTION = "action"
    SEVERITY = "severity"
    CERTAINTY = "certainty"
    EVALUATION = "evaluation"


class Platform(StrEnum):
    REDDIT = "reddit"
    YOUTUBE = "youtube"


class SourceType(StrEnum):
    NEWS_OUTLET = "news_outlet"
    WIRE_SERVICE = "wire_service"
    BROADCASTER = "broadcaster"
    OFFICIAL = "official"
    OTHER = "other"

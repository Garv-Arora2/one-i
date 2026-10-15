"""Tunable thresholds for the analysis modules.

Every number here is a deliberate, documented choice. They live in one place so
that they can be inspected, changed and evaluated against the labelled set in
`backend/evaluation/`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroupingConfig:
    """Deciding whether two articles describe the same event."""

    text_weight: float = 0.55
    entity_weight: float = 0.25
    title_weight: float = 0.20
    # Articles further apart than this are never grouped.
    max_hours_apart: float = 96.0
    # Inside the window, time proximity scales the score between this floor and
    # 1.0. It nudges, it does not veto: a legitimate next-day follow-up must
    # still be able to join its event.
    min_time_factor: float = 0.5
    # Chosen with backend/evaluation/grouping_pairs.py: on the demo dataset,
    # same-event pairs score >= 0.12 and different-event pairs <= 0.03.
    link_threshold: float = 0.10
    min_shared_entities: int = 1
    # Same-story headlines that NER missed (no shared entity) still link if
    # titles or leads overlap this strongly.
    title_link_floor: float = 0.28
    text_link_floor: float = 0.20


@dataclass(frozen=True)
class PublicationConfig:
    """What is worth showing on the site.

    ONE I compares sources. A single-outlet item cannot show a difference, so
    it is not published. Beyond that, an event is only published when its
    reporting can actually power the product: developments for the timeline
    and coverage grid, which numbers and wording then attach to. Thinly
    reported items stay stored (a later ingest may corroborate them) but are
    never listed. The front page keeps a short run of well-covered
    events — about three to four pages — rather than an infinite archive.
    """

    min_sources: int = 2
    # A live event needs at least this many developments before it is
    # published. One development gives a one-row coverage grid and nothing to
    # compare; two is the minimum for timeline, coverage and crux to work.
    min_developments_for_live: int = 2
    page_size: int = 16
    max_pages: int = 4


@dataclass(frozen=True)
class DevelopmentConfig:
    """Turning article sentences into chronological developments."""

    min_sentence_chars: int = 45
    max_sentence_chars: int = 320
    cluster_threshold: float = 0.34
    # A development must be reported by at least this many distinct sources,
    # unless the event only has one source at all.
    min_supporting_sources: int = 2
    max_developments: int = 12
    keywords_per_development: int = 6


@dataclass(frozen=True)
class CoverageConfig:
    """Deciding whether an article reports a development."""

    covered_threshold: float = 0.42
    unclear_threshold: float = 0.22
    sentence_weight: float = 0.55
    keyword_weight: float = 0.45
    # An article published before a development (minus this grace period)
    # could not have reported it, so it is excluded from the coverage rate.
    timing_grace_hours: float = 2.0


@dataclass(frozen=True)
class NumberConfig:
    """Extracting and comparing numerical claims."""

    subject_tokens: int = 4
    subject_key_tokens: int = 3
    # Values within this relative distance are treated as agreement.
    agreement_relative_tolerance: float = 0.02
    agreement_absolute_tolerance: float = 0.05


@dataclass(frozen=True)
class WordingConfig:
    """Comparing how sources described the same development."""

    # Passages must be similar enough to be about the same thing ...
    comparable_min_similarity: float = 0.18
    # Short RSS headlines share fewer words, so the floor is lower.
    short_item_min_similarity: float = 0.12
    # ... but near-identical text is not a meaningful difference.
    identical_max_similarity: float = 0.92
    min_sources_for_comparison: int = 2


@dataclass(frozen=True)
class MarketConfig:
    """Predefined event windows, fixed before looking at any result."""

    baseline_days: int = 5
    window_days: int = 2
    min_points_required: int = 2


GROUPING = GroupingConfig()
DEVELOPMENTS = DevelopmentConfig()
COVERAGE = CoverageConfig()
NUMBERS = NumberConfig()
WORDING = WordingConfig()
MARKET = MarketConfig()
PUBLICATION = PublicationConfig()

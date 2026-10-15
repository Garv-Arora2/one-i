from datetime import datetime, timedelta, timezone

from app.analysis.coverage import (
    ArticleForCoverage,
    CoverageDecision,
    DevelopmentForCoverage,
    assess_coverage,
    coverage_rate,
    coverage_rate_by_source,
)
from app.models.enums import CoverageStatus

BASE = datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc)

DEVELOPMENT = DevelopmentForCoverage(
    id=1,
    text="Meridian County officials ordered the evacuation of residents living near the plant.",
    keywords=["meridian county", "evacuation", "residents", "plant"],
    occurred_at=BASE,
)


def decision_for(article: ArticleForCoverage) -> CoverageDecision:
    return assess_coverage([DEVELOPMENT], [article])[0]


def test_article_reporting_the_development_is_marked_covered():
    article = ArticleForCoverage(
        id=1,
        source_id=1,
        title="Evacuation ordered near the Fairmont Hollow plant",
        content=(
            "Meridian County officials ordered the evacuation of residents living near the "
            "plant on Tuesday morning. Shelters opened at two schools."
        ),
        published_at=BASE + timedelta(hours=1),
    )
    result = decision_for(article)
    assert result.status is CoverageStatus.COVERED
    assert "evacuation" in result.matched_terms


def test_unrelated_article_is_marked_not_covered():
    article = ArticleForCoverage(
        id=2,
        source_id=2,
        title="Council approves Harbourside housing plan",
        content="Meridian City Council approved a housing plan for the former rail yard.",
        published_at=BASE + timedelta(hours=1),
    )
    assert decision_for(article).status is CoverageStatus.NOT_COVERED


def test_partial_evidence_is_reported_as_unclear():
    article = ArticleForCoverage(
        id=3,
        source_id=3,
        title="Traffic disruption around the plant",
        content=(
            "Drivers were asked to avoid roads near the plant. Some residents said they had "
            "left the area. The county did not comment on the wider situation."
        ),
        published_at=BASE + timedelta(hours=1),
    )
    assert decision_for(article).status in {CoverageStatus.UNCLEAR, CoverageStatus.NOT_COVERED}


def test_article_published_before_the_development_is_not_applicable():
    article = ArticleForCoverage(
        id=4,
        source_id=4,
        title="Plant operating normally",
        content="The Fairmont Hollow plant was operating normally, the company said.",
        published_at=BASE - timedelta(hours=8),
    )
    result = decision_for(article)
    assert result.status is CoverageStatus.NOT_APPLICABLE
    assert result.is_applicable is False


def test_coverage_rate_excludes_not_applicable_articles():
    decisions = [
        CoverageDecision(1, 1, 1, CoverageStatus.COVERED, 0.9, []),
        CoverageDecision(1, 2, 2, CoverageStatus.NOT_COVERED, 0.1, []),
        CoverageDecision(1, 3, 3, CoverageStatus.NOT_APPLICABLE, 0.0, []),
    ]
    assert coverage_rate(decisions) == 0.5


def test_coverage_rate_is_none_when_nothing_is_applicable():
    decisions = [CoverageDecision(1, 1, 1, CoverageStatus.NOT_APPLICABLE, 0.0, [])]
    assert coverage_rate(decisions) is None


def test_coverage_rate_by_source():
    decisions = [
        CoverageDecision(1, 1, 10, CoverageStatus.COVERED, 0.9, []),
        CoverageDecision(2, 2, 10, CoverageStatus.NOT_COVERED, 0.1, []),
        CoverageDecision(1, 3, 20, CoverageStatus.COVERED, 0.8, []),
    ]
    rates = coverage_rate_by_source(decisions)
    assert rates[10] == 0.5
    assert rates[20] == 1.0


def test_no_developments_produces_no_decisions():
    assert assess_coverage([], []) == []

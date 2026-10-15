from datetime import datetime, timedelta, timezone

from app.analysis.crux import CruxArticle, CruxDevelopment, build_crux, format_value
from app.analysis.numbers import build_comparisons, extract_numbers
from app.analysis.reaction import ReactionItem, aggregate_reactions, deduplicate_reactions, event_terms
from app.models.enums import ValueKind

BASE = datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc)

DEVELOPMENTS = [
    CruxDevelopment(
        id=1,
        title="Meridian County officials ordered the evacuation of residents",
        description="Meridian County officials ordered the evacuation of residents near the plant in Fairmont Hollow.",
        occurred_at=BASE,
        importance=0.9,
        supporting_article_ids=[1, 2],
    ),
    CruxDevelopment(
        id=2,
        title="Meridian County lifted the evacuation order",
        description="Meridian County lifted the evacuation order for Fairmont Hollow on Wednesday.",
        occurred_at=BASE + timedelta(days=1),
        importance=0.5,
        supporting_article_ids=[3],
    ),
]

ARTICLES = [
    CruxArticle(id=1, source_id=1, source_name="A", published_at=BASE),
    CruxArticle(id=2, source_id=2, source_name="B", published_at=BASE + timedelta(hours=2)),
    CruxArticle(id=3, source_id=3, source_name="C", published_at=BASE + timedelta(days=1)),
]


def test_crux_is_built_from_stored_developments():
    result = build_crux(
        title="Chemical leak in Fairmont Hollow",
        event_time=BASE,
        location="Fairmont Hollow",
        developments=DEVELOPMENTS,
        number_comparisons=[],
        articles=ARTICLES,
    )
    assert "ordered the evacuation" in result.text
    assert any(part.label == "Where" for part in result.parts)
    assert all(part.article_ids or part.label in {"Who is involved"} for part in result.parts)


def test_crux_stays_within_the_word_budget():
    long_developments = [
        CruxDevelopment(
            id=index,
            title="A development " * 20,
            description="A development sentence that is quite long. " * 6,
            occurred_at=BASE + timedelta(hours=index),
            importance=0.5,
            supporting_article_ids=[1],
        )
        for index in range(6)
    ]
    result = build_crux(
        title="Event",
        event_time=BASE,
        location=None,
        developments=long_developments,
        number_comparisons=[],
        articles=ARTICLES,
    )
    assert len(result.text.split()) <= 260


def test_crux_falls_back_to_the_title_without_developments():
    result = build_crux(
        title="Chemical leak in Fairmont Hollow",
        event_time=None,
        location=None,
        developments=[],
        number_comparisons=[],
        articles=ARTICLES,
    )
    assert result.text.startswith("Chemical leak in Fairmont Hollow")


def test_crux_context_reports_provenance():
    result = build_crux(
        title="Event",
        event_time=BASE,
        location=None,
        developments=DEVELOPMENTS,
        number_comparisons=[],
        articles=ARTICLES,
    )
    assert "3 articles" in result.context_text
    assert "3 sources" in result.context_text


def test_crux_reports_disagreeing_numbers_as_a_range():
    left = extract_numbers(1, 1, "t", "County records show that 3,200 residents were evacuated from the area.")
    right = extract_numbers(2, 2, "t", "About 4,000 residents were evacuated from the area.")
    comparisons = build_comparisons(left + right)
    result = build_crux(
        title="Event",
        event_time=BASE,
        location=None,
        developments=DEVELOPMENTS,
        number_comparisons=comparisons,
        articles=ARTICLES,
    )
    assert "reported between" in result.text


def test_format_value_distinguishes_units():
    assert format_value(30, ValueKind.PERCENT, "%") == "30%"
    assert format_value(10, ValueKind.PERCENTAGE_POINT, None) == "10 percentage points"
    assert format_value(3200, ValueKind.COUNT, "residents") == "3,200 residents"


def reaction(identifier: int, text: str, engagement: int = 10) -> ReactionItem:
    return ReactionItem(
        id=identifier,
        platform="reddit",
        content=text,
        published_at=BASE + timedelta(hours=identifier),
        engagement=engagement,
        url=f"https://example.com/{identifier}",
        community="r/meridian",
    )


def test_reactions_are_deduplicated():
    items = [reaction(1, "The evacuation order came through at 6am"), reaction(2, "The evacuation order came through at 6am")]
    assert len(deduplicate_reactions(items)) == 1


TERMS = event_terms("Chemical leak forces evacuation in Fairmont Hollow")


def test_reaction_summary_reports_volume_and_timing():
    items = [
        reaction(1, "The evacuation order came through this morning and the shelters filled quickly"),
        reaction(2, "The evacuation order was lifted and residents returned to their homes"),
        reaction(3, "Air quality readings should be published in full by the county"),
        reaction(4, "Air quality readings matter more than the company statement"),
    ]
    summary = aggregate_reactions(items, TERMS)
    assert summary.available is True
    assert summary.total == 4
    assert summary.by_platform["reddit"]["posts"] == 4
    assert summary.timeline


def test_highlights_are_the_most_liked_comments_about_the_event():
    items = [
        reaction(1, "The evacuation was handled badly by the county", engagement=40),
        reaction(2, "Subscribe to my channel for more videos like this one", engagement=900),
        reaction(3, "The leak should never have happened at that plant", engagement=75),
        reaction(4, "first!!", engagement=500),
        reaction(5, "Full story on the leak here https://example.com/leak", engagement=300),
    ]
    summary = aggregate_reactions(items, TERMS)
    assert [item.id for item in summary.highlights] == [3, 1]


def test_no_reactions_reports_an_explicit_unavailable_state():
    summary = aggregate_reactions([], TERMS)
    assert summary.available is False
    assert summary.unavailable_reason

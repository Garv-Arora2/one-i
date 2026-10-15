from datetime import datetime, timedelta, timezone

from app.analysis.reaction import ReactionItem, event_terms, is_relevant, looks_english
from app.services.reaction_service import (
    SearchPlan,
    event_search_query,
    headline_word_frequency,
    ongoing_topics,
    plan_search,
    query_from_title,
    topic_from_breadcrumbs,
)


def test_topic_prefers_most_common_deepest_breadcrumb_without_year():
    contents = [
        "Disasters and accidents › 2026 Atlantic hurricane season › Hurricane Isaias — story one",
        "Disasters and accidents › Hurricane Isaias — story two",
        "Disasters and accidents › 2026 Atlantic hurricane season — story three",
    ]
    assert topic_from_breadcrumbs(contents) == "Hurricane Isaias"


def test_topic_strips_year_ranges():
    contents = ["Politics › 2025–2026 Iran–United States negotiations — talks resume"] * 2
    assert topic_from_breadcrumbs(contents) == "Iran–United States negotiations"


def test_topic_from_a_single_stray_article_is_not_trusted():
    contents = ["Law and crime › 2026 Erie shooting — unrelated story", "plain body"]
    assert topic_from_breadcrumbs(contents) is None


def test_ongoing_topic_is_pinned_with_rarest_headline_names():
    day = datetime(2026, 6, 1, tzinfo=timezone.utc)
    rows = [(f"Sports › 2026 FIFA World Cup — match {i}", day + timedelta(days=i)) for i in range(5)]
    rows += [("Disasters › Hurricane Isaias — landfall", day)] * 2
    ongoing = ongoing_topics(rows)
    assert ongoing == {"FIFA World Cup"}

    frequency = headline_word_frequency(["World news today"] * 5 + ["Ivory Coast wins"])
    plan = plan_search(
        "In association football, Ivory Coast reaches the knockout stage of the FIFA World Cup",
        ["Sports › 2026 FIFA World Cup — Ivory Coast reaches knockouts"] * 2,
        ongoing,
        frequency,
    )
    assert plan.query == "FIFA World Cup Ivory Coast"
    assert plan.anchors == ("Ivory", "Coast")

    specific = plan_search("Hurricane Isaias weakens", ["Disasters › Hurricane Isaias — x"] * 2, ongoing)
    assert specific == SearchPlan("Hurricane Isaias")


def test_topic_ignores_section_only_and_plain_bodies():
    assert topic_from_breadcrumbs(["Sports — a story", "Plain body — with a dash", ""]) is None


def test_title_query_keeps_proper_nouns_and_headline_order():
    query = query_from_title("War-damaged Gaza building collapses, killing at least 20 people")
    assert query.split()[:2] == ["War-damaged", "Gaza"]
    assert len(query.split()) <= 6
    assert "20" not in query


def test_search_query_falls_back_to_title():
    assert event_search_query("Tiger attacks man at England wildlife park", ["no crumbs"]).startswith(
        "Tiger"
    )


def _item(index: int, text: str, likes: int = 0) -> ReactionItem:
    return ReactionItem(id=index, platform="youtube", content=text, engagement=likes)


def test_short_and_non_english_comments_are_not_readable():
    assert not looks_english("lol")
    assert not looks_english("🔥🔥🔥")
    assert not looks_english("Это ужасная новость для всех нас")
    assert looks_english("This is terrible news for the people of Gaza")


def test_comment_must_share_a_word_with_the_event():
    terms = event_terms("War-damaged Gaza building collapses, killing at least 20 people")
    assert is_relevant(_item(1, "Praying for everyone in Gaza tonight"), terms)
    assert not is_relevant(_item(2, "What a great goal in the second half"), terms)

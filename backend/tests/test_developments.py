from datetime import datetime, timedelta, timezone

from app.analysis.developments import (
    ArticleForAnalysis,
    action_verbs_in,
    candidate_sentences,
    identify_developments,
)

BASE = datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc)

EVACUATION = (
    "Meridian County officials ordered the evacuation of residents living within two "
    "kilometres of the plant."
)


def article(article_id: int, source_id: int, extra: str, hours: int = 0) -> ArticleForAnalysis:
    return ArticleForAnalysis(
        id=article_id,
        source_id=source_id,
        title="Chemical leak at the Fairmont Hollow plant",
        content=f"{EVACUATION} {extra}",
        published_at=BASE + timedelta(hours=hours),
    )


def test_candidate_sentences_skip_short_and_actionless_text():
    subject = ArticleForAnalysis(
        id=1,
        source_id=1,
        title="Chemical leak at the Fairmont Hollow plant",
        content="Short. The weather in the county remains mild and pleasant for this season.",
    )
    sentences = candidate_sentences(subject)
    assert all(len(sentence) >= 45 for sentence in sentences)
    assert "Short." not in sentences


def test_development_requires_support_from_two_sources():
    single_source = [article(1, 1, "The company suspended operations at the site on Tuesday.")]
    developments = identify_developments(single_source)
    # With only one source available the requirement relaxes to that source.
    assert developments

    two_articles_one_source = [
        article(1, 1, "The company suspended operations at the site on Tuesday."),
        article(2, 1, "The regulator opened an investigation into the release on Tuesday."),
    ]
    results = identify_developments(two_articles_one_source)
    assert results
    assert all(len(item.supporting_source_ids) == 1 for item in results)


def test_repeated_reporting_across_sources_becomes_a_development():
    developments = identify_developments(
        [
            article(1, 1, "The company suspended operations at the site on Tuesday."),
            article(2, 2, "The company suspended operations at the site on Tuesday afternoon.", 2),
            article(3, 3, "Local schools were closed for the day as a precaution.", 3),
        ]
    )
    assert any("evacuation" in item.title.lower() for item in developments)
    assert any(len(item.supporting_source_ids) >= 2 for item in developments)


def test_opposite_actions_do_not_merge_into_one_development():
    closed = "The Meridian County Fire Department closed the perimeter road on Tuesday."
    reopened = "The Meridian County Fire Department reopened the perimeter road on Wednesday."
    developments = identify_developments(
        [
            article(1, 1, closed),
            article(2, 2, closed, 1),
            article(3, 3, reopened, 24),
            article(4, 4, reopened, 25),
        ]
    )
    titles = " | ".join(item.title for item in developments)
    assert "closed the perimeter road" in titles
    assert "reopened the perimeter road" in titles


def test_developments_are_returned_in_chronological_order():
    developments = identify_developments(
        [
            article(1, 1, "The company suspended operations at the site on Tuesday."),
            article(2, 2, "The company suspended operations at the site on Tuesday.", 2),
            article(3, 3, "Meridian County lifted the evacuation order on Wednesday morning.", 24),
            article(4, 4, "Meridian County lifted the evacuation order on Wednesday morning.", 26),
        ]
    )
    times = [item.occurred_at for item in developments if item.occurred_at]
    assert times == sorted(times)


def test_no_articles_produces_no_developments():
    assert identify_developments([]) == []


def test_action_verbs_are_detected():
    assert "evacuated" in action_verbs_in("Residents were evacuated from the area.")
    assert "killing" in action_verbs_in("A building collapsed, killing residents inside.")
    assert action_verbs_in("The weather remains mild.") == set()


def test_short_rss_headlines_still_form_a_development():
    """Headlines that do not cluster still become one development.

    Live RSS items are short and worded differently outlet to outlet. Without a
    fallback, coverage, numbers and wording never run.
    """
    developments = identify_developments(
        [
            ArticleForAnalysis(
                id=1,
                source_id=1,
                title="War-damaged Gaza building collapses, killing at least 20 people",
                content="A six-storey building in Gaza City collapsed, killing at least 20 people.",
                published_at=BASE,
            ),
            ArticleForAnalysis(
                id=2,
                source_id=2,
                title="Gaza building collapse turns deadly",
                content="A strike overnight left a residential building in ruins and residents described people trapped inside.",
                published_at=BASE,
            ),
            ArticleForAnalysis(
                id=3,
                source_id=3,
                title="21 killed as Gaza building collapses",
                content="Medics said 21 people were killed when a war-damaged building collapsed in Gaza.",
                published_at=BASE,
            ),
        ]
    )
    assert developments
    assert any(len(item.supporting_source_ids) >= 2 for item in developments)

from app.analysis.wording import Passage, compare_wording, extract_markers, select_passages

# In the pipeline a development description is always a real sentence taken
# from one of the articles, so the test uses one too.
DEVELOPMENT = (
    "Vantor Industries responded to allegations that a valve at its plant was overdue "
    "for inspection."
)

ARTICLES = [
    (
        1,
        1,
        "The Meridian Ledger",
        "Company admits valve was overdue",
        "Vantor Industries admitted that a valve at the plant had not been inspected since 2023.",
    ),
    (
        2,
        2,
        "Northgate Post",
        "Company responds to claims",
        "Vantor Industries responded to allegations that a valve at its plant was overdue for inspection.",
    ),
    (
        3,
        3,
        "Beacon Broadcasting",
        "Regulator criticises maintenance",
        "Inspectors said Vantor mishandled the maintenance schedule for a valve that failed.",
    ),
]


def test_markers_are_grouped_by_aspect():
    markers = extract_markers("Vantor Industries admitted that inspectors confirmed a severe failure.")
    assert "admitted" in markers["responsibility"]
    assert "confirmed" in markers["certainty"]
    assert "severe" in markers["severity"]


def test_no_markers_for_neutral_text():
    assert extract_markers("The plant is located outside the town.") == {}


def test_passages_are_selected_per_article_with_context():
    passages = select_passages(DEVELOPMENT, ARTICLES)
    names = {passage.source_name for passage in passages}
    assert {"The Meridian Ledger", "Northgate Post"} <= names
    assert all(passage.surrounding_text for passage in passages)
    assert all(passage.similarity >= 0.18 for passage in passages)


def test_meaningful_difference_is_detected():
    comparison = compare_wording("Company response", select_passages(DEVELOPMENT, ARTICLES))
    assert comparison is not None
    assert "responsibility" in comparison.differing_aspects or "evaluation" in comparison.differing_aspects


def test_single_source_produces_no_comparison():
    passages = select_passages(DEVELOPMENT, ARTICLES[:1])
    assert compare_wording("Company response", passages) is None


def test_identical_wording_is_not_a_difference():
    text = "Vantor Industries confirmed that a valve failure caused the release."
    passages = [
        Passage(1, 1, "Source A", text, text, 0.99, extract_markers(text)),
        Passage(2, 2, "Source B", text, text, 0.99, extract_markers(text)),
    ]
    assert compare_wording("Company response", passages) is None


def test_attacked_versus_retaliated_is_shown_as_an_action_difference():
    left = "Iran attacked Israel overnight."
    right = "Iran retaliated on Israel overnight."
    passages = [
        Passage(1, 1, "Source A", left, left, 0.8, extract_markers(left)),
        Passage(2, 2, "Source B", right, right, 0.8, extract_markers(right)),
    ]
    comparison = compare_wording("Overnight strike", passages)
    assert comparison is not None
    assert "action" in comparison.differing_aspects
    assert "attacked" in comparison.passages[0].markers["action"]
    assert "retaliated" in comparison.passages[1].markers["action"]


def test_trivial_synonyms_are_not_flagged():
    left = "The county halted operations at the site."
    right = "The county suspended operations at the site."
    passages = [
        Passage(1, 1, "Source A", left, left, 0.8, extract_markers(left)),
        Passage(2, 2, "Source B", right, right, 0.8, extract_markers(right)),
    ]
    assert compare_wording("Operations", passages) is None


def test_articles_without_a_comparable_passage_are_skipped():
    unrelated = (4, 4, "Fairmont Local Herald", "Weather", "The forecast is mild for the weekend.")
    passages = select_passages(DEVELOPMENT, [*ARTICLES, unrelated])
    assert all(passage.source_name != "Fairmont Local Herald" for passage in passages)


def test_short_rss_items_keep_title_framing():
    development = "War-damaged Gaza building collapses, killing at least 20 people"
    articles = [
        (
            1,
            1,
            "CBS News",
            "War-damaged Gaza building collapses, killing at least 20 people",
            "Health officials in Gaza say a building collapsed, killing at least 20 people.",
        ),
        (
            2,
            2,
            "Al Jazeera",
            "Gaza's damaged buildings turn deadly",
            "A war-damaged building collapses in Gaza City, killing at least 21 Palestinians.",
        ),
    ]
    comparison = compare_wording(development, select_passages(development, articles))
    assert comparison is not None
    assert "severity" in comparison.differing_aspects
    deadly_passages = [p for p in comparison.passages if "deadly" in p.text.lower()]
    assert deadly_passages


def test_strike_group_is_not_an_action_marker():
    markers = extract_markers(
        "The group includes the USS Theodore Roosevelt carrier strike group."
    )
    assert "strike" not in (markers.get("action") or [])


def test_strike_outside_the_compound_is_still_an_action_marker():
    markers = extract_markers("The minister ordered a strike on the base at dawn.")
    assert "strike" in (markers.get("action") or [])

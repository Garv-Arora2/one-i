from datetime import datetime, timedelta, timezone

from app.analysis.grouping import (
    ArticleForGrouping,
    _distinctive_entities,
    articles_describe_same_event,
    common_entities,
    group_articles,
    score_pairs,
    storm_names,
)

BASE = datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc)

LEAK_A = ArticleForGrouping(
    id=1,
    title="Chemical leak at Vantor Industries plant forces evacuation in Fairmont Hollow",
    content=(
        "A chemical leak was detected at the Vantor Industries plant in Fairmont Hollow. "
        "Meridian County officials ordered the evacuation of residents near the plant."
    ),
    published_at=BASE,
)
LEAK_B = ArticleForGrouping(
    id=2,
    title="Vantor Industries responds after solvent release near Fairmont Hollow",
    content=(
        "Vantor Industries responded after a solvent release at its Fairmont Hollow plant. "
        "Meridian County officials ordered the evacuation of residents living near the plant."
    ),
    published_at=BASE + timedelta(hours=3),
)
HOUSING = ArticleForGrouping(
    id=3,
    title="Meridian City Council approves Harbourside housing plan",
    content=(
        "Meridian City Council approved the Harbourside housing plan, allowing construction "
        "of homes on the former Harbourside rail yard."
    ),
    published_at=BASE - timedelta(days=2),
)


def test_articles_about_the_same_event_are_grouped():
    clusters = group_articles([LEAK_A, LEAK_B, HOUSING])
    grouped = {tuple(sorted(cluster.article_ids)) for cluster in clusters}
    assert (1, 2) in grouped
    assert (3,) in grouped


def test_unrelated_articles_score_far_below_related_ones():
    scores = {(pair.left_id, pair.right_id): pair.score for pair in score_pairs([LEAK_A, LEAK_B, HOUSING])}
    assert scores[(1, 2)] > scores[(1, 3)] * 3


def test_articles_outside_the_time_window_are_not_linked():
    far_away = ArticleForGrouping(
        id=4, title=LEAK_B.title, content=LEAK_B.content, published_at=BASE + timedelta(days=10)
    )
    pair = score_pairs([LEAK_A, far_away])[0]
    assert pair.linked is False
    assert pair.score == 0.0


def test_single_article_still_produces_an_event():
    clusters = group_articles([LEAK_A])
    assert len(clusters) == 1
    assert clusters[0].article_ids == [1]


def test_empty_input_produces_no_clusters():
    assert group_articles([]) == []


def test_missing_publication_times_do_not_crash_grouping():
    undated = ArticleForGrouping(id=5, title=LEAK_B.title, content=LEAK_B.content, published_at=None)
    clusters = group_articles([LEAK_A, undated])
    assert sum(len(cluster.article_ids) for cluster in clusters) == 2


def test_cluster_reports_keywords_and_event_time():
    cluster = next(
        cluster for cluster in group_articles([LEAK_A, LEAK_B]) if len(cluster.article_ids) == 2
    )
    assert cluster.event_time == BASE
    assert cluster.keywords


def test_matching_headlines_group_even_without_named_entities():
    left = ArticleForGrouping(
        id=10,
        title="Belarus frees 25 political prisoners in return for US sanctions relief",
        content="Belarus has freed twenty-five political prisoners after talks on sanctions relief.",
        published_at=BASE,
        source_id=1,
    )
    right = ArticleForGrouping(
        id=11,
        title="Belarus Frees 25 Political Prisoners in Exchange for U.S. Sanctions Relief",
        content="The release of 25 political prisoners was tied to a US sanctions relief deal.",
        published_at=BASE,
        source_id=2,
    )
    clusters = group_articles([left, right])
    assert any(sorted(cluster.article_ids) == [10, 11] for cluster in clusters)


def test_sharing_only_a_country_name_does_not_group_unrelated_stories():
    mine = ArticleForGrouping(
        id=20,
        title="Gold mine collapse in Sudan kills at least 70",
        content="A gold mine collapse in a remote area of Sudan has killed at least 70 people.",
        published_at=BASE,
        source_id=1,
    )
    politics = ArticleForGrouping(
        id=21,
        title="Sudanese opposition leader returns from exile",
        content="An opposition leader returned to Khartoum after years in exile.",
        published_at=BASE,
        source_id=2,
    )
    clusters = group_articles([mine, politics])
    grouped = {tuple(sorted(cluster.article_ids)) for cluster in clusters}
    assert (20, 21) not in grouped


def test_pruning_far_apart_pairs_keeps_the_same_links():
    """keep_unlinked=False must not change clustering, only the workload."""
    articles = []
    for day in range(0, 60, 10):
        articles.append(
            ArticleForGrouping(
                id=100 + day,
                title=LEAK_B.title,
                content=LEAK_B.content,
                published_at=BASE + timedelta(days=day),
            )
        )
    articles.extend([LEAK_A, LEAK_B, HOUSING])
    full = score_pairs(articles)
    pruned = score_pairs(articles, keep_unlinked=False)
    full_links = {(p.left_id, p.right_id) for p in full if p.linked}
    pruned_links = {(p.left_id, p.right_id) for p in pruned if p.linked}
    assert full_links == pruned_links
    assert len(pruned) < len(full)


def test_widespread_names_stop_counting_as_distinctive():
    sets = [{f"story{i}", "trump"} for i in range(12)]
    common = common_entities(sets)
    assert "trump" in common
    assert "story0" not in common
    assert _distinctive_entities(["trump"], common) == []
    assert _distinctive_entities(["fairmont hollow"], common) == ["fairmont hollow"]


def test_small_inputs_have_no_widespread_names():
    sets = [{"vantor", "fairmont"}, {"vantor", "meridian"}]
    assert common_entities(sets) == frozenset()


def test_sharing_only_a_widespread_name_does_not_link():
    assert (
        articles_describe_same_event(
            score=0.15,
            shared_entities=["trump"],
            title_overlap=0.1,
            text_similarity=0.1,
            common_entities_set=frozenset({"trump"}),
        )
        is False
    )
    assert (
        articles_describe_same_event(
            score=0.15,
            shared_entities=["trump"],
            title_overlap=0.1,
            text_similarity=0.1,
        )
        is True
    )


def test_storm_names_ignore_non_name_words():
    assert storm_names("Hurricane Simon hits Mexico", "The National Hurricane Center said.") == {"simon"}
    assert storm_names("Category 4 storm surge expected", "") == frozenset()


def test_two_different_named_storms_never_link():
    isaias = ArticleForGrouping(
        id=1,
        title="Hurricane Isaias makes landfall as a Category 4 hurricane, thousands without power",
        content="Hurricane Isaias made landfall as a powerful Category 4 hurricane with damaging winds.",
        published_at=BASE,
    )
    simon = ArticleForGrouping(
        id=2,
        title="Hurricane Simon makes landfall as a Category 4 hurricane, thousands without power",
        content="Hurricane Simon made landfall as a powerful Category 4 hurricane with damaging winds.",
        published_at=BASE + timedelta(hours=2),
    )
    isaias_again = ArticleForGrouping(
        id=3,
        title="Hurricane Isaias leaves thousands without power after landfall",
        content="Hurricane Isaias left thousands without power after it made landfall.",
        published_at=BASE + timedelta(hours=3),
    )
    links = {(p.left_id, p.right_id) for p in score_pairs([isaias, simon, isaias_again]) if p.linked}
    assert (1, 2) not in links and (2, 3) not in links
    assert (1, 3) in links

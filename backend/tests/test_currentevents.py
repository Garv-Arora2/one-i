"""Tests for the Wikipedia current-events history inlet (pure parser)."""

from datetime import date

from app.ingestion.providers.currentevents import _page_title, parse_day

_SAMPLE = """{{Current events|year=2026|month=10|day=11|top=yes|content=}}
<!-- All news items below this line -->
'''Armed conflicts and attacks'''
*[[Middle Eastern crisis (2023–present)|Middle Eastern crisis]]
**[[Yemeni civil war (2014–present)|Yemeni civil war]]
***Missile fire on an airport terminal causes a fire and injures several people. [https://news.sky.com/story/example-1 (Sky News)] [https://www.aljazeera.com/news/example-2 (Al Jazeera)]
***A minister resigns after the attack. [https://www.example.com/spanish-story (Example <small>in Spanish</small>)]
'''Disasters and accidents'''
*A flood sweeps away houses in a mountain district after days of heavy rain, and rescue teams say that more people are missing. [https://www.example.com/flood (Example News)]
*Short. [https://www.example.com/x (Example News)]
"""


def test_page_title_has_no_zero_padded_day():
    assert _page_title(date(2026, 10, 5)) == "Portal:Current events/2026 October 5"


def test_parse_day_emits_one_article_per_citation():
    articles = parse_day(_SAMPLE, date(2026, 10, 11))
    by_url = {article.url: article for article in articles}
    assert len(articles) == 3  # 2 missile cites + flood; Spanish + stub skipped
    sky = by_url["https://news.sky.com/story/example-1"]
    assert sky.source_name == "Sky News"
    assert sky.provider == "currentevents"
    assert sky.published_at is not None and sky.published_at.day == 11
    assert "airport terminal" in sky.title
    assert "Armed conflicts" in sky.content  # breadcrumb kept for context


def test_parse_day_skips_non_english_labels_and_stubs():
    articles = parse_day(_SAMPLE, date(2026, 10, 11))
    urls = [article.url for article in articles]
    assert not any("spanish-story" in url for url in urls)
    assert not any(url.endswith("/x") for url in urls)


def test_template_language_labels_are_skipped():
    sample = (
        "'''Armed conflicts and attacks'''\n"
        "*A drone strike hits a power station near the border, officials say, cutting power to thousands. "
        "[https://www.polsatnews.pl/story (Polsat News {{small|in Polish}})] "
        "[https://www.example.com/en (Example News)]\n"
    )
    articles = parse_day(sample, date(2026, 10, 11))
    assert [article.source_name for article in articles] == ["Example News"]


def test_parse_day_cleans_wikilinks():
    articles = parse_day(_SAMPLE, date(2026, 10, 11))
    for article in articles:
        assert "[[" not in article.title and "[[" not in article.content

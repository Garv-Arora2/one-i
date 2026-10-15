from app.analysis.developments import ArticleForAnalysis
from app.models import Article
from app.services.analysis_service import _outlet_worded, is_summary_only

SUMMARY = "Sports › 2026 FIFA World Cup — The 1,000th FIFA World Cup match is held in Monterrey."


def _article(article_id: int, provider: str, title: str, content: str) -> Article:
    return Article(id=article_id, source_id=article_id, title=title, content=content, url="u", ingest_provider=provider)


def _analysis(article: Article) -> ArticleForAnalysis:
    return ArticleForAnalysis(
        id=article.id, source_id=article.source_id, title=article.title, content=article.content
    )


def test_wikipedia_summary_rows_are_never_quoted_as_outlet_wording():
    stub = _article(1, "currentevents", "The 1,000th match is held.", SUMMARY)
    bare = _article(2, "currentevents", "Same text.", "Same text.")
    fetched = _article(3, "currentevents", "Wikipedia's sentence.", "The outlet's own page text. " * 30)
    rss = _article(4, "rss", "Outlet headline", "Outlet body text.")
    assert is_summary_only(stub) and is_summary_only(bare)
    assert not is_summary_only(fetched) and not is_summary_only(rss)

    articles = [stub, bare, fetched, rss]
    quotable = _outlet_worded(articles, [_analysis(a) for a in articles])
    assert [item.id for item in quotable] == [3, 4]
    # A fetched current-events row keeps the page text but drops Wikipedia's title.
    assert quotable[0].title == ""
    assert quotable[1].title == "Outlet headline"

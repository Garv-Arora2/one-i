from sqlalchemy import select

from app.ingestion.default_feeds import canonical_domain
from app.ingestion.store import get_or_create_source, tidy_sources
from app.models import Article, Source


def test_alias_domains_resolve_to_one_outlet():
    assert canonical_domain("www.bbc.com") == "bbc.co.uk"
    assert canonical_domain("edition.cnn.com") == "cnn.com"
    assert canonical_domain("guardian.ng") == "guardian.ng"


def test_new_articles_from_an_alias_domain_join_the_canonical_source(empty_session):
    first = get_or_create_source(
        empty_session, name="BBC News", domain="bbc.co.uk", source_type="news_outlet", is_demo=False
    )
    second = get_or_create_source(
        empty_session, name="BBC", domain="bbc.com", source_type="news_outlet", is_demo=False
    )
    assert first.id == second.id


def test_existing_alias_sources_are_merged(empty_session):
    canonical = Source(name="CNN", domain="cnn.com", source_type="news_outlet", is_demo=False)
    alias = Source(name="CNN", domain="edition.cnn.com", source_type="news_outlet", is_demo=False)
    empty_session.add_all([canonical, alias])
    empty_session.flush()
    empty_session.add(
        Article(source_id=alias.id, title="Report", url="https://edition.cnn.com/a", content="Text")
    )
    empty_session.flush()

    assert tidy_sources(empty_session) == 1
    article = empty_session.scalar(select(Article).where(Article.url == "https://edition.cnn.com/a"))
    assert article.source_id == canonical.id
    assert empty_session.scalar(select(Source).where(Source.domain == "edition.cnn.com")) is None


def test_feed_titles_and_wiki_markup_are_replaced_by_outlet_names(empty_session):
    sky = Source(
        name="World News - Breaking international news and headlines | Sky News",
        domain="news.sky.com",
        source_type="news_outlet",
        is_demo=False,
    )
    polsat = Source(
        name="Polsat News {{small|in Polish}}", domain="polsatnews.pl", source_type="news_outlet", is_demo=False
    )
    empty_session.add_all([sky, polsat])
    empty_session.flush()
    tidy_sources(empty_session)
    assert sky.name == "Sky News"
    assert polsat.name == "Polsat News"

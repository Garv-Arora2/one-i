import pytest

from app.ingestion.providers.base import ProviderError
from app.ingestion.providers.market import parse_alpha_vantage_payload
from app.ingestion.providers.newsapi import NewsApiProvider, parse_newsapi_payload
from app.ingestion.providers.reddit import RedditProvider, parse_reddit_payload
from app.ingestion.default_feeds import DEFAULT_RSS_FEEDS, parse_rss_feeds
from app.ingestion.providers.rss import RssNewsProvider, parse_feed
from app.ingestion.providers.youtube import (
    YouTubeProvider,
    YouTubeVideo,
    is_relevant_video,
    parse_youtube_comments,
    parse_youtube_videos,
)

RSS = """<?xml version="1.0"?>
<rss version="2.0"><channel>
  <title>Calder Wire Service</title>
  <item>
    <title>Chemical release reported at the plant</title>
    <link>https://calderwire.example/story-1</link>
    <pubDate>Tue, 03 Mar 2026 07:45:00 GMT</pubDate>
    <description>&lt;p&gt;A chemical release was detected at the plant after midnight inspections.&lt;/p&gt;</description>
  </item>
  <item>
    <title>Item without a link</title>
    <description>Should be skipped.</description>
  </item>
</channel></rss>"""

ATOM = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Beacon Broadcasting</title>
  <entry>
    <title>Regulator opens investigation</title>
    <link href="https://beaconbroadcasting.example/story-2"/>
    <published>2026-03-03T14:30:00Z</published>
    <summary>The regulator opened an investigation.</summary>
  </entry>
</feed>"""


def test_rss_feed_is_parsed():
    articles = parse_feed(RSS, "https://calderwire.example/feed")
    assert len(articles) == 1
    assert articles[0].url == "https://calderwire.example/story-1"
    assert articles[0].published_at is not None
    assert "<p>" not in articles[0].content
    assert "midnight inspections" in articles[0].content


def test_default_rss_feeds_are_https_urls():
    assert DEFAULT_RSS_FEEDS
    assert all(url.startswith("https://") for url in DEFAULT_RSS_FEEDS)


def test_empty_rss_feeds_setting_uses_the_default_list():
    assert parse_rss_feeds("") == list(DEFAULT_RSS_FEEDS)
    assert parse_rss_feeds("off") == []
    assert parse_rss_feeds("https://calderwire.example/feed") == [
        "https://calderwire.example/feed"
    ]


def test_known_outlet_domains_use_a_short_name():
    xml = RSS.replace(
        "https://calderwire.example/story-1", "https://www.bbc.co.uk/news/world-1"
    )
    articles = parse_feed(xml, "https://feeds.bbci.co.uk/news/world/rss.xml")
    assert articles[0].source_name == "BBC News"
    assert articles[0].source_domain == "bbc.co.uk"


def test_atom_feed_is_parsed():
    articles = parse_feed(ATOM, "https://beaconbroadcasting.example/feed")
    assert articles[0].source_domain == "beaconbroadcasting.example"


def test_unconfigured_rss_provider_returns_nothing():
    provider = RssNewsProvider([])
    assert provider.is_configured() is False
    assert provider.fetch_articles() == []


def test_newsapi_payload_is_mapped():
    payload = {
        "status": "ok",
        "articles": [
            {
                "source": {"name": "Calder Wire Service"},
                "title": "Chemical release reported",
                "url": "https://calderwire.example/story-1",
                "description": "A chemical release was detected.",
                "content": "More text.",
                "publishedAt": "2026-03-03T07:45:00Z",
            },
            {"source": {}, "title": "", "url": ""},
        ],
    }
    articles = parse_newsapi_payload(payload)
    assert len(articles) == 1
    assert articles[0].source_name == "Calder Wire Service"


def test_newsapi_error_payload_raises():
    with pytest.raises(ProviderError):
        parse_newsapi_payload({"status": "error", "message": "rate limited"})


def test_unconfigured_newsapi_provider_returns_nothing():
    provider = NewsApiProvider("", "https://newsapi.org/v2")
    assert provider.fetch_articles() == []
    assert "NEWS_API_KEY" in provider.configuration_hint()


def test_reddit_payload_is_mapped():
    payload = {
        "data": {
            "children": [
                {
                    "data": {
                        "id": "abc",
                        "title": "Anyone near the plant?",
                        "selftext": "The order came through this morning.",
                        "score": 42,
                        "created_utc": 1772000000,
                        "permalink": "/r/meridian/comments/abc",
                        "subreddit_name_prefixed": "r/meridian",
                    }
                },
                {"data": {"id": "", "title": ""}},
            ]
        }
    }
    reactions = parse_reddit_payload(payload)
    assert len(reactions) == 1
    assert reactions[0].engagement == 42
    assert reactions[0].url.startswith("https://www.reddit.com/")


def test_reddit_provider_reports_missing_configuration():
    provider = RedditProvider("", "", "one-i/1.0")
    assert provider.fetch_reactions("query") == []
    assert "REDDIT_CLIENT_ID" in provider.configuration_hint()


def test_youtube_payloads_are_mapped():
    search = {
        "items": [
            {
                "id": {"videoId": "vid1"},
                "snippet": {
                    "title": "Explaining the evacuation",
                    "description": "What we know so far.",
                    "publishedAt": "2026-03-03T13:30:00Z",
                    "channelTitle": "Meridian Daily Brief",
                },
            }
        ]
    }
    comments = {
        "items": [
            {
                "id": "c1",
                "snippet": {
                    "topLevelComment": {
                        "snippet": {
                            "textOriginal": "The information was slower than it should have been.",
                            "likeCount": 12,
                            "publishedAt": "2026-03-03T16:10:00Z",
                        }
                    }
                },
            }
        ]
    }
    video = parse_youtube_videos(search)[0]
    assert video.video_id == "vid1"
    assert video.channel == "Meridian Daily Brief"
    comment = parse_youtube_comments(comments, video)[0]
    assert comment.engagement == 12
    assert comment.url == "https://www.youtube.com/watch?v=vid1&lc=c1"
    assert comment.community == "Meridian Daily Brief"


def _video(title: str, description: str = "") -> YouTubeVideo:
    return YouTubeVideo("v", title, description, "Channel", None)


def test_youtube_relevance_needs_two_query_words():
    assert is_relevant_video("Hurricane Isaias", _video("Hurricane Isaias makes landfall"))
    assert not is_relevant_video("Hurricane Isaias", _video("Hurricane season explained"))
    assert is_relevant_video(
        "Poland school stabbings", _video("Warsaw school stabbing", "Police in Poland said")
    )
    assert is_relevant_video("Ebola", _video("What is Ebola?"))
    assert is_relevant_video("Ebola epidemic", _video("Ebola outbreak in Uganda"))
    assert not is_relevant_video("", _video("Anything"))


def test_youtube_anchors_pin_broad_topics_to_the_event():
    query, anchors = "FIFA World Cup Ivory Coast", ("Ivory", "Coast")
    assert not is_relevant_video(query, _video("Shakira - FIFA World Cup official song"), anchors)
    assert is_relevant_video(query, _video("Ivory Coast vs Cape Verde | FIFA World Cup"), anchors)


def test_youtube_provider_reports_missing_configuration():
    provider = YouTubeProvider("")
    assert provider.fetch_reactions("query") == []


def test_market_payload_is_mapped_and_sorted():
    payload = {
        "Time Series (Daily)": {
            "2026-03-03": {"4. close": "45.73", "5. volume": "4600000"},
            "2026-03-02": {"4. close": "48.75", "5. volume": "1150000"},
            "2026-03-01": {"4. close": "bad", "5. volume": "1"},
        }
    }
    points = parse_alpha_vantage_payload(payload, "VNTR")
    assert [point.price for point in points] == [48.75, 45.73]


def test_market_rate_limit_payload_raises():
    with pytest.raises(ProviderError):
        parse_alpha_vantage_payload({"Note": "rate limit"}, "VNTR")


def test_market_missing_series_raises():
    with pytest.raises(ProviderError):
        parse_alpha_vantage_payload({}, "VNTR")

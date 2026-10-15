from datetime import datetime, timezone

import pytest

from app.ingestion.providers.base import ProviderError
from app.ingestion.providers.gdelt import (
    GdeltNewsProvider,
    parse_gdelt_payload,
    parse_seendate,
)


def test_parse_seendate_handles_gdelt_format():
    parsed = parse_seendate("20261011T153000Z")
    assert parsed == datetime(2026, 10, 11, 15, 30, tzinfo=timezone.utc)


def test_parse_seendate_returns_none_for_blank():
    assert parse_seendate(None) is None
    assert parse_seendate("") is None


def test_parse_gdelt_payload_maps_articles():
    payload = {
        "articles": [
            {
                "url": "https://example.com/a",
                "title": "Parliament approves the emergency budget after a long debate",
                "seendate": "20261011T153000Z",
                "sourceCommonName": "Example Times",
                "domain": "example.com",
            },
            {"url": "not-a-url", "title": "Bad row"},
            {"url": "https://example.com/b", "title": ""},
        ]
    }
    articles = parse_gdelt_payload(payload)
    assert len(articles) == 1
    article = articles[0]
    assert article.source_name == "Example Times"
    assert article.provider == "gdelt"
    assert article.published_at == datetime(2026, 10, 11, 15, 30, tzinfo=timezone.utc)


def test_parse_gdelt_payload_rejects_bad_shape():
    with pytest.raises(ProviderError):
        parse_gdelt_payload({"status": "error", "message": "quota"})
    with pytest.raises(ProviderError):
        parse_gdelt_payload({})


def test_disabled_provider_is_not_configured():
    provider = GdeltNewsProvider(enabled=False)
    assert not provider.is_configured()
    assert provider.fetch_articles(limit=10) == []


def test_backfill_windows_cover_the_requested_days():
    provider = GdeltNewsProvider()
    windows = provider.backfill_windows(16, chunk_days=7)
    assert len(windows) == 3
    total_days = sum((end - start).total_seconds() / 86400 for start, end in windows)
    assert total_days == pytest.approx(16)
    # Newest first and contiguous.
    for (older_start, older_end), (newer_start, newer_end) in zip(
        windows[1:], windows[:-1]
    ):
        assert newer_start == older_end
        assert older_start < older_end
        assert newer_start < newer_end

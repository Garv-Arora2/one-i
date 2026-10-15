"""API behaviour against a database seeded with the fictional demo dataset."""

from __future__ import annotations

import pytest

FORBIDDEN_LANGUAGE = (
    "intentionally omitted",
    "lied",
    "manipulated",
    "bias score",
    "truth score",
    "credibility score",
)


@pytest.fixture
def leak_event(client):
    events = client.get("/events").json()["events"]
    return next(event for event in events if "Vantor" in event["title"])


def test_health_reports_database_connectivity(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["database_connected"] is True
    assert body["events"] >= 3


def test_status_lists_provider_configuration(client):
    body = client.get("/status").json()
    names = {provider["name"] for provider in body["providers"]}
    assert {"rss", "newsapi", "reddit", "youtube", "alphavantage"} <= names
    assert body["demo_events"] >= 3


def test_event_list_returns_summaries(client):
    body = client.get("/events").json()
    assert body["total"] >= 3
    first = body["events"][0]
    assert first["article_count"] > 0
    assert first["source_count"] > 0
    assert first["is_demo"] is True


def test_event_list_dataset_filter(client):
    assert client.get("/events?dataset=live").json()["total"] == 0
    assert client.get("/events?dataset=demo").json()["total"] >= 3


def test_event_list_sort_orders_by_event_time(client):
    recent = client.get("/events?dataset=demo&sort=recent").json()["events"]
    oldest = client.get("/events?dataset=demo&sort=oldest").json()["events"]
    assert recent and oldest
    assert [event["id"] for event in recent] == [
        event["id"] for event in reversed(oldest)
    ]
    assert client.get("/events?dataset=demo&sort=bogus").status_code == 422


def test_event_list_hides_thinly_covered_events(client):
    """The front page is for comparisons, so one-outlet items are not listed."""
    listed = client.get("/events?min_sources=2").json()["events"]
    assert listed
    assert all(event["source_count"] >= 2 for event in listed)
    assert client.get("/events?min_sources=5").json()["total"] == 1
    assert client.get("/events?min_sources=20").json()["total"] == 0


def test_event_list_rejects_invalid_pagination(client):
    assert client.get("/events?limit=0").status_code == 422
    assert client.get("/events?dataset=whatever").status_code == 422


def test_event_detail_includes_crux_and_sources(client, leak_event):
    body = client.get(f"/events/{leak_event['slug']}").json()
    assert body["crux"]
    assert body["crux_parts"]
    assert body["context_parts"]
    assert len(body["articles"]) == 7
    assert all(article["url"].startswith("https://") for article in body["articles"])


def test_crux_is_the_opening_statement_not_the_whole_account(client, leak_event):
    """The crux field is a readable standfirst; the rest is in crux_parts."""
    body = client.get(f"/events/{leak_event['slug']}").json()
    assert body["crux"] == body["crux_parts"][0]["text"]
    assert "Who is involved:" not in body["crux"]


def test_event_can_be_fetched_by_id_or_slug(client, leak_event):
    by_id = client.get(f"/events/{leak_event['id']}").json()
    by_slug = client.get(f"/events/{leak_event['slug']}").json()
    assert by_id["id"] == by_slug["id"]


def test_unknown_event_returns_404(client):
    response = client.get("/events/does-not-exist")
    assert response.status_code == 404
    assert "No event found" in response.json()["detail"]


def test_timeline_is_chronological(client, leak_event):
    developments = client.get(f"/events/{leak_event['id']}/timeline").json()["developments"]
    times = [item["occurred_at"] for item in developments if item["occurred_at"]]
    assert times == sorted(times)
    assert len(developments) >= 3


def test_coverage_reports_rates_and_states(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/coverage").json()
    assert body["sources"]
    assert body["overall_coverage_rate"] is not None
    statuses = {cell["status"] for cell in body["cells"]}
    assert statuses <= {"covered", "unclear", "not_covered", "not_applicable"}
    assert "covered" in statuses


def test_coverage_marks_earlier_articles_as_not_applicable(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/coverage").json()
    assert any(cell["status"] == "not_applicable" for cell in body["cells"])


def test_coverage_developments_carry_a_short_title(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/coverage").json()
    assert body["developments"]
    for development in body["developments"]:
        assert development["short_title"]
        assert len(development["short_title"].split()) <= len(development["title"].split())


def test_comparisons_expose_number_differences_with_context(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/comparisons").json()
    subjects = {item["subject"] for item in body["numbers"]}
    assert any("resident" in subject for subject in subjects)
    disagreement = next(item for item in body["numbers"] if not item["sources_agree"])
    assert disagreement["difference"] > 0
    assert len({item["source"]["id"] for item in disagreement["observations"]}) >= 2
    assert all(item["context"] for item in disagreement["observations"])


def test_percentage_differences_are_expressed_in_percentage_points(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/comparisons").json()
    percent = [item for item in body["numbers"] if item["value_kind"] == "percent"]
    assert percent
    assert all(item["difference_unit"] == "percentage points" for item in percent)


def test_comparisons_expose_wording_differences_with_quotes(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/comparisons").json()
    assert body["wording"]
    passage = body["wording"][0]["passages"][0]
    assert passage["quoted_text"]
    assert passage["surrounding_text"]
    assert passage["article_url"].startswith("https://")


def test_reactions_include_volume_and_disclaimer(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/reactions").json()
    assert body["available"] is True
    assert body["total"] > 0
    assert set(body["by_platform"]) <= {"reddit", "youtube"}
    assert "not evidence" in body["disclaimer"]


def test_market_is_available_for_the_connected_event(client, leak_event):
    body = client.get(f"/events/{leak_event['id']}/market").json()
    assert body["available"] is True
    assert body["symbol"] == "VNTR"
    assert body["return_percent"] < 0
    assert body["benchmark_symbol"] == "MRDX"
    assert body["difference_percentage_points"] is not None
    assert "does not establish" in body["disclaimer"]


def test_market_is_explicitly_unavailable_for_other_events(client):
    events = client.get("/events").json()["events"]
    other = next(event for event in events if not event["has_market_data"])
    body = client.get(f"/events/{other['id']}/market").json()
    assert body["available"] is False
    assert body["unavailable_reason"]
    assert body["series"] == []


def test_sources_endpoint_lists_tracked_sources(client):
    body = client.get("/sources").json()
    assert body["total"] >= 5
    assert all(source["domain"].endswith(".example") for source in body["sources"])


def test_source_detail_includes_per_event_coverage(client):
    source_id = client.get("/sources").json()["sources"][0]["id"]
    body = client.get(f"/sources/{source_id}").json()
    assert body["events"]
    assert "coverage_rate" in body["events"][0]


def test_unknown_source_returns_404(client):
    assert client.get("/sources/99999").status_code == 404


def test_api_never_uses_accusatory_language(client, leak_event):
    payloads = " ".join(
        client.get(f"/events/{leak_event['id']}{suffix}").text.lower()
        for suffix in ["", "/timeline", "/coverage", "/comparisons", "/reactions", "/market"]
    )
    for phrase in FORBIDDEN_LANGUAGE:
        assert phrase not in payloads

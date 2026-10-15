from datetime import datetime, timezone

from app.ingestion.dedupe import deduplicate
from app.ingestion.normalize import (
    NormalizedArticle,
    RejectedArticle,
    normalize_article,
    normalize_batch,
)
from app.ingestion.providers.base import RawArticle

BODY = (
    "Meridian County officials ordered the evacuation of residents living within two "
    "kilometres of the plant after a chemical release was detected on Tuesday morning."
)


def raw(**overrides) -> RawArticle:
    defaults = dict(
        source_name="Calder Wire Service",
        source_domain="calderwire.example",
        title="Chemical release reported at the Fairmont Hollow plant",
        url="https://calderwire.example/story?utm_source=newsletter",
        content=BODY,
        published_at=datetime(2026, 3, 3, 7, 45, tzinfo=timezone.utc),
        provider="test",
    )
    defaults.update(overrides)
    return RawArticle(**defaults)


def test_normalize_accepts_a_complete_article():
    result = normalize_article(raw())
    assert isinstance(result, NormalizedArticle)
    assert result.url == "https://calderwire.example/story"
    assert result.content_hash


def test_normalize_rejects_missing_url():
    assert isinstance(normalize_article(raw(url="")), RejectedArticle)


def test_normalize_rejects_short_title():
    result = normalize_article(raw(title="Leak"))
    assert isinstance(result, RejectedArticle)
    assert "title" in result.reason


def test_normalize_rejects_thin_body():
    result = normalize_article(raw(content="Too short."))
    assert isinstance(result, RejectedArticle)
    assert "too short" in result.reason


def test_normalize_rejects_non_english_reporting():
    italian = raw(
        url="https://example.com/dolore",
        title="Dove finisce il dolore comincia la speranza",
        content=(
            "Dove finisce il dolore comincia la speranza, ha detto il presidente "
            "durante la cerimonia in piazza davanti alla folla riunita."
        ),
    )
    result = normalize_article(italian)
    assert isinstance(result, RejectedArticle)
    assert "English" in result.reason


def test_normalize_rejects_german_reporting_with_stray_matches():
    german = raw(
        url="https://example.com/herat",
        title="Hoffnungszeichen aus Herat: Neuer Glasbetrieb in Afghanistan",
        content=(
            "Hoffnungszeichen aus Herat in Afghanistan, wo der neue Glasbetrieb "
            "in der Provinz die Produktion in der Region verdoppelt hat."
        ),
    )
    assert isinstance(normalize_article(german), RejectedArticle)


def test_normalize_rejects_long_foreign_body_with_lookalike_words():
    albanian = raw(
        url="https://example.com/tirane",
        title="Me ka ndaluar sherbimi sekret ne Maqedoni",
        content=(
            "Me ka ndaluar sherbimi sekret ne Maqedoni. Do te shkojme ne Tirane "
            "heret ne mengjes, do te flasim me gazetaret. Ndalimi eshte politike, "
            "thone ata qe e dine historine e vendit tone te dashur."
        ),
    )
    assert isinstance(normalize_article(albanian), RejectedArticle)


def test_normalize_accepts_short_english_wire_blurb():
    blurb = raw(
        url="https://example.com/storm",
        title="Hurricane Simon lashes Mexico's Pacific coast as a powerful Category 4 storm",
        content=(
            "Hurricane Simon lashes Mexico's Pacific coast as a powerful Category 4 "
            "storm. Simon strengthened into a powerful Category 4 hurricane as it "
            "barreled toward Mexico's Pacific coast."
        ),
    )
    assert isinstance(normalize_article(blurb), NormalizedArticle)


def test_normalize_accepts_english_body():
    assert isinstance(normalize_article(raw()), NormalizedArticle)


def test_normalize_falls_back_to_url_domain():
    result = normalize_article(raw(source_domain=""))
    assert isinstance(result, NormalizedArticle)
    assert result.source_domain == "calderwire.example"


def test_normalize_keeps_missing_publication_time_as_none():
    result = normalize_article(raw(published_at=None))
    assert isinstance(result, NormalizedArticle)
    assert result.published_at is None


def test_normalize_batch_separates_accepted_and_rejected():
    accepted, rejected = normalize_batch([raw(), raw(url="not-a-url")])
    assert len(accepted) == 1
    assert len(rejected) == 1


def test_deduplicate_removes_same_url_after_canonicalisation():
    first = normalize_article(raw())
    second = normalize_article(raw(url="https://calderwire.example/story?utm_campaign=x"))
    unique, duplicates = deduplicate([first, second])
    assert len(unique) == 1
    assert duplicates[0].reason == "same url"


def test_deduplicate_removes_identical_text_at_a_different_url():
    first = normalize_article(raw())
    second = normalize_article(raw(url="https://calderwire.example/story-copy"))
    unique, duplicates = deduplicate([first, second])
    assert len(unique) == 1
    assert duplicates[0].reason == "identical text"


def test_deduplicate_removes_near_identical_title_from_same_source():
    first = normalize_article(raw())
    second = normalize_article(
        raw(
            url="https://calderwire.example/story-update",
            title="Chemical release reported at the Fairmont Hollow plant",
            content=BODY + " The perimeter road was closed to traffic.",
        )
    )
    unique, duplicates = deduplicate([first, second])
    assert len(unique) == 1
    assert "near-identical" in duplicates[0].reason


def test_deduplicate_keeps_same_headline_from_different_sources():
    first = normalize_article(raw())
    second = normalize_article(
        raw(
            source_domain="northgatepost.example",
            url="https://northgatepost.example/story",
            content=BODY + " A spokesperson declined to comment further.",
        )
    )
    unique, _ = deduplicate([first, second])
    assert len(unique) == 2


def test_deduplicate_keeps_earliest_version():
    early = normalize_article(raw(published_at=datetime(2026, 3, 3, 7, 0, tzinfo=timezone.utc)))
    late = normalize_article(
        raw(
            url="https://calderwire.example/story-late",
            published_at=datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc),
        )
    )
    unique, _ = deduplicate([late, early])
    assert unique[0].url == "https://calderwire.example/story"

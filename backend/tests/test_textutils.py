from app.analysis.textutils import (
    canonicalize_url,
    clean_text,
    content_fingerprint,
    domain_of,
    normalize_title,
    short_title,
    slugify,
    split_sentences,
    token_set,
    truncate_words,
)


def test_clean_text_strips_markup_and_collapses_whitespace():
    assert clean_text("  <p>Hello   <b>world</b></p>\n\n") == "Hello world"


def test_clean_text_handles_none_and_empty():
    assert clean_text(None) == ""
    assert clean_text("") == ""


def test_clean_text_strips_invisible_format_characters():
    assert clean_text("Kosovo\u2060s former President") == "Kosovos former President"
    assert "\u2060" not in clean_text("a\u2060b")
    assert clean_text("a\u2060b") == "ab"
    assert clean_text("a\u200bb") == "ab"


def test_normalize_title_removes_outlet_suffix():
    assert normalize_title("Plant closed after leak - Northgate Post") == "Plant closed after leak"
    assert normalize_title("Plant closed after leak | Beacon") == "Plant closed after leak"


def test_normalize_title_rejoins_tokenised_punctuation():
    assert normalize_title("Troops head to Mideast as U . S . President weighs strikes") == (
        "Troops head to Mideast as U.S. President weighs strikes"
    )
    assert normalize_title("Chronicles of Victory ( October 2 , 2020 ): interview") == (
        "Chronicles of Victory (October 2, 2020): interview"
    )


def test_split_sentences_protects_abbreviations():
    sentences = split_sentences("Dr. Alvez spoke on Monday. The plant closed.")
    assert sentences == ["Dr. Alvez spoke on Monday.", "The plant closed."]


def test_split_sentences_handles_closing_quotes_and_month_abbreviations():
    text = 'He said recovery "could be challenging." 4 dead as the storm weakens. It began on Oct. 7 near the coast.'
    assert split_sentences(text) == [
        'He said recovery "could be challenging."',
        "4 dead as the storm weakens.",
        "It began on Oct. 7 near the coast.",
    ]


def test_canonicalize_url_removes_tracking_and_normalises_host():
    assert (
        canonicalize_url("https://WWW.Example.com/story/?utm_source=x&id=4&utm_medium=y")
        == "https://example.com/story?id=4"
    )


def test_canonicalize_url_is_stable_for_trailing_slash():
    assert canonicalize_url("https://example.com/a/") == canonicalize_url("https://example.com/a")


def test_domain_of_handles_missing_scheme():
    assert domain_of("www.example.com/story") == "example.com"
    assert domain_of(None) == ""


def test_content_fingerprint_ignores_formatting_but_not_content():
    first = content_fingerprint("Leak at plant", "<p>Residents   were evacuated.</p>")
    second = content_fingerprint("Leak at plant", "Residents were evacuated.")
    third = content_fingerprint("Leak at plant", "Nobody was evacuated today anywhere.")
    assert first == second
    assert first != third


def test_token_set_drops_stopwords():
    assert "the" not in token_set("The plant closed")
    assert "plant" in token_set("The plant closed")


def test_slugify_and_truncate():
    assert slugify("Leak at Vantor Industries!") == "leak-at-vantor-industries"
    assert truncate_words("one two three four", 2) == "one two…"
    assert truncate_words("one two", 5) == "one two"


def test_short_title_prefers_a_clause_boundary():
    text = (
        "It includes the USS Theodore Roosevelt carrier strike group, which recently "
        "deployed with the cruiser USS Chosin, and the USS Makin Island group"
    )
    assert short_title(text, 14) == "It includes the USS Theodore Roosevelt carrier strike group…"


def test_short_title_leaves_short_text_alone():
    assert short_title("Parliament approved the budget", 14) == "Parliament approved the budget"


def test_topic_breadcrumb_is_stripped_but_ordinary_dashes_are_kept():
    from app.analysis.textutils import strip_topic_breadcrumb

    crumb = 'Sports › 2026 FIFA World Cup › Tunisia v Japan — The 1,000th match is held.'
    assert strip_topic_breadcrumb(crumb) == 'The 1,000th match is held.'
    plain = 'Officials said — after a pause — that 20 people died.'
    assert strip_topic_breadcrumb(plain) == plain

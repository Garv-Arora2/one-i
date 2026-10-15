from app.ingestion.enrich import extract_article_text


HTML = """
<html><head><title>Site</title><script>var x=1</script></head>
<body>
<nav>Home World Sport</nav>
<article>
  <h1>Gold mine collapse in Sudan kills at least 70</h1>
  <p>A gold mine collapse in a remote area of Sudan has killed at least 70 people, a charity said on Monday.</p>
  <p>Dozens more are missing after shafts collapsed on Sunday, according to rescue workers at the scene.</p>
  <aside>Subscribe for more news</aside>
  <p>Local officials said the search for survivors would continue overnight.</p>
</article>
<footer>All rights reserved</footer>
</body></html>
"""


def test_extract_article_text_keeps_paragraphs_and_drops_chrome():
    body = extract_article_text(HTML)
    assert "killed at least 70 people" in body
    assert "Dozens more are missing" in body
    assert "Subscribe for more news" not in body
    assert "var x=1" not in body
    assert "Home World Sport" not in body


def test_extract_article_text_returns_empty_for_blank_html():
    assert extract_article_text("") == ""
    assert extract_article_text("<html><body></body></html>") == ""


def test_extract_article_text_drops_related_story_rails():
    html = """
    <html><body><article>
      <h1>Ceasefire talks continue in the capital</h1>
      <p>Negotiators met for a second day of ceasefire talks in the capital on Monday, and officials said both delegations would remain at the table until every outstanding point had been fully addressed by all sides.</p>
      <div class="related-stories">
        <p>Protesters detained after election chief ouster</p>
        <p>Airport strike causes fire, day after attack kills many</p>
      </div>
      <p>The talks are expected to resume again on Tuesday morning.</p>
    </article></body></html>
    """
    body = extract_article_text(html)
    assert "second day of ceasefire talks" in body
    assert "resume again on Tuesday" in body
    assert "Protesters detained" not in body
    assert "Airport strike causes fire" not in body


def test_extract_article_text_drops_boilerplate_lines():
    html = """
    <html><body><article>
      <h1>Ceasefire talks continue in the capital</h1>
      <p>Skip to main content</p>
      <p>Negotiators met for a second day of ceasefire talks in the capital on Monday, officials said.</p>
      <p>Cover image: staff photographer</p>
    </article></body></html>
    """
    body = extract_article_text(html)
    assert "Skip to main content" not in body
    assert "Cover image" not in body
    assert "second day of ceasefire talks" in body


RAIL = "Protesters seeking election chief ouster were detained by police on Monday morning."


def _long_body(story: str) -> str:
    filler = (
        " Negotiators met for a second day of talks in the capital while officials "
        "from both delegations said every outstanding point would be fully addressed."
    )
    return story + filler + " " + RAIL + filler


def test_find_repeated_sentences_spots_outlet_rails():
    from app.ingestion.enrich import find_repeated_sentences

    bodies = {i: _long_body(f"Story number {i} unfolded with dramatic developments today. " * 6) for i in range(5)}
    repeated = find_repeated_sentences(bodies)
    keys = list(repeated)
    assert any("protesters seeking election chief" in key for key in keys)
    # a sentence unique to one body is not flagged
    assert not any("story number 0 unfolded" in key for key in keys)


def test_find_repeated_sentences_ignores_short_bodies():
    from app.ingestion.enrich import find_repeated_sentences

    bodies = {i: RAIL for i in range(6)}
    assert find_repeated_sentences(bodies) == {}


def test_find_repeated_sentences_spots_unpunctuated_rails():
    from app.ingestion.enrich import find_repeated_sentences

    rail = (
        "Protesters seeking election chief ouster detained "
        "Saudi-led coalition says airport strike causes fire "
        "Pope Leo says he will undergo surgery for small growth"
    )
    bodies = {
        i: ("Story number %d unfolded with dramatic developments today. " % i) * 20 + rail
        for i in range(3)
    }
    repeated = find_repeated_sentences(bodies)
    assert any("saudi-led coalition says airport strike" in key for key in repeated)

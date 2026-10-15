"""Public RSS outlets ONE I reads when RSS_FEEDS is not set.

These are original-outlet feeds, not a news aggregator. Override with
RSS_FEEDS, or set RSS_FEEDS=off to disable RSS entirely.
"""

from __future__ import annotations

DEFAULT_RSS_FEEDS: tuple[str, ...] = (
    "https://feeds.bbci.co.uk/news/world/rss.xml",
    "https://www.theguardian.com/world/rss",
    "https://feeds.npr.org/1004/rss.xml",
    "https://www.aljazeera.com/xml/rss/all.xml",
    "https://rss.nytimes.com/services/xml/rss/nyt/World.xml",
    "https://www.independent.co.uk/news/world/rss",
    "https://www.cbsnews.com/latest/rss/world",
    "https://abcnews.go.com/abcnews/internationalheadlines",
    "https://rss.dw.com/rdf/rss-en-all",
    "https://www.france24.com/en/rss",
    "https://feeds.skynews.com/feeds/rss/world.xml",
    "https://www.cbc.ca/webfeed/rss/rss-world",
    "https://www.pbs.org/newshour/feeds/rss/world",
)

OUTLET_NAMES: dict[str, str] = {
    "bbc.co.uk": "BBC News",
    "bbc.com": "BBC News",
    "theguardian.com": "The Guardian",
    "npr.org": "NPR",
    "aljazeera.com": "Al Jazeera",
    "nytimes.com": "The New York Times",
    "cbsnews.com": "CBS News",
    "abcnews.com": "ABC News",
    "abcnews.go.com": "ABC News",
    "independent.co.uk": "The Independent",
    "dw.com": "DW News",
    "france24.com": "France 24",
    "skynews.com": "Sky News",
    "news.sky.com": "Sky News",
    "cbc.ca": "CBC News",
    "pbs.org": "PBS NewsHour",
}

# Alternate web addresses of the same newsroom. Without this, one outlet is
# stored twice and can be "compared" with itself. Same-named but separate
# papers (The Guardian vs guardian.ng) are deliberately not listed.
DOMAIN_ALIASES: dict[str, str] = {
    "bbc.com": "bbc.co.uk",
    "edition.cnn.com": "cnn.com",
    "aje.news": "aljazeera.com",
    "arab.news": "arabnews.com",
    "amp.scmp.com": "scmp.com",
    "m.economictimes.com": "economictimes.indiatimes.com",
    "the-independent.com": "independent.co.uk",
    "koreajoongangdaily.joins.com": "koreajoongangdaily.com",
    "globalnation.inquirer.net": "newsinfo.inquirer.net",
    "business.inquirer.net": "newsinfo.inquirer.net",
    "africa.espn.com": "espn.com",
}

_DISABLED = frozenset({"off", "none", "disabled"})


def canonical_domain(domain: str) -> str:
    key = (domain or "").lower().removeprefix("www.")
    return DOMAIN_ALIASES.get(key, key)


def outlet_name_for(domain: str, fallback: str = "") -> str:
    return OUTLET_NAMES.get(canonical_domain(domain), fallback)


def parse_rss_feeds(value: str | None) -> list[str]:
    """Return configured feed URLs, falling back to the default outlet list."""
    raw = (value or "").strip()
    if raw.lower() in _DISABLED:
        return []
    urls = [url.strip() for url in raw.split(",") if url.strip()]
    return urls or list(DEFAULT_RSS_FEEDS)

"""Wikipedia Portal:Current events provider.

Keyless, structured history inlet: each daily archive page lists the day's
significant world stories as bullets, each citing 1+ real news-source URLs.
One RawArticle is emitted per (story, citation URL), so the same story told
by several outlets naturally merges into one well-sourced event downstream.

Page titles look like ``Portal:Current events/2026 October 11`` (MediaWiki
namespace 100). Fetched via the ``action=parse`` API (wikitext), 1 request
per day, with a small politeness delay.
"""

from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime, timedelta, timezone
from urllib.parse import urlparse

import httpx

from app.ingestion.normalize import is_english_reporting
from app.ingestion.providers.base import NewsProvider, RawArticle

log = logging.getLogger(__name__)

API_URL = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "ONE-I research project (news event analysis; contact: researcher@example.com)"
REQUEST_DELAY_S = 0.4
TIMEOUT_S = 30.0

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_RE_SECTION = re.compile(r"^'''(.*?)'''\s*$")
_RE_BULLET = re.compile(r"^(\*+)\s*(.*)$")
_RE_CITE = re.compile(r"\[(https?://[^\s\]]+)\s+([^]]*)\]")
_RE_WIKILINK = re.compile(r"\[\[([^|\]]*\|)?([^\]]+)\]\]")
_RE_ITALIC = re.compile(r"''+")


# "(in Spanish)" or the template form "{{small|in Polish}}".
_RE_NON_ENGLISH_LABEL = re.compile(r"(?:\(|\|)\s*in\s+[A-Z][a-z]+\s*(?:\)|\}\})")
_RE_TEMPLATE = re.compile(r"\{\{[^}]*\}\}")


def _page_title(day: date) -> str:
    return f"Portal:Current events/{day.year} {_MONTHS[day.month - 1]} {day.day}"


def _clean_text(raw: str) -> str:
    text = _RE_WIKILINK.sub(r"\2", raw)
    text = _RE_ITALIC.sub("", text)
    text = text.replace("�", "-")  # Wikipedia ships U+FFFD where a dash belongs
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _clean_outlet(label: str, url: str) -> str:
    name = _clean_text(_RE_TEMPLATE.sub("", label)).strip().strip("'\"()")
    # "ANI via Gulf News" -> "Gulf News"; "X, via Y" -> keep as-is otherwise
    if " via " in name:
        name = name.split(" via ")[-1].strip()
    if not name:
        host = re.sub(r"^www\.", "", url.split("/")[2].lower())
        name = host.split(".")[0].replace("-", " ").title()
    return name[:80]


def _fetch_wikitext(client: httpx.Client, day: date) -> str | None:
    try:
        resp = client.get(
            API_URL,
            params={
                "action": "parse",
                "page": _page_title(day),
                "prop": "wikitext",
                "format": "json",
            },
            timeout=TIMEOUT_S,
        )
        if resp.status_code != 200:
            log.warning("currentevents %s: HTTP %s", day, resp.status_code)
            return None
        data = resp.json()
        if "error" in data:
            return None  # page does not exist (too old / future)
        return data["parse"]["wikitext"]["*"]
    except Exception as exc:  # network hiccups: skip the day
        log.warning("currentevents %s: %s", day, exc)
        return None


def parse_day(wikitext: str, day: date) -> list[RawArticle]:
    """Parse one daily archive page into raw articles (pure function)."""
    articles: list[RawArticle] = []
    section = ""
    stack: list[str] = []  # topic breadcrumb by bullet depth
    published = datetime(day.year, day.month, day.day, 12, 0, tzinfo=timezone.utc)

    for line in wikitext.splitlines():
        line = line.strip()
        if not line or line.startswith("{{") or line.startswith("<!--"):
            continue
        m_sec = _RE_SECTION.match(line)
        if m_sec:
            section = _clean_text(m_sec.group(1))
            stack = []
            continue
        m_bul = _RE_BULLET.match(line)
        if not m_bul:
            continue
        depth = len(m_bul.group(1))
        body = m_bul.group(2).strip()
        cites = _RE_CITE.findall(body)
        story = _clean_text(_RE_CITE.sub("", body)).strip(" ;:,.—-")
        # maintain breadcrumb: parent topics are shallower bullets
        stack = stack[: max(0, depth - 1)]
        if cites and len(story) >= 40:
            crumb = " › ".join([p for p in [section, *stack] if p])
            for url, label in cites:
                if _RE_NON_ENGLISH_LABEL.search(label or "") and "English" not in (label or ""):
                    continue  # e.g. "(in Spanish)": body would fail the English gate
                url = url.strip()
                domain = re.sub(r"^www\.", "", urlparse(url).netloc.lower())
                outlet = _clean_outlet(label, url)
                title = story[:300]
                if not is_english_reporting(title, ""):
                    continue
                articles.append(
                    RawArticle(
                        source_name=outlet,
                        source_domain=domain,
                        title=title,
                        url=url,
                        content=(f"{crumb} — {title}"[:2000] if crumb else title),
                        published_at=published,
                        provider="currentevents",
                    )
                )
        elif len(story) >= 3:
            # topic-only bullet: extend breadcrumb for deeper stories
            topic = story[:120]
            if len(stack) < depth:
                stack.append(topic)
            else:
                stack[depth - 1 :] = [topic]
    return articles


def fetch_range(start: date, end: date) -> list[RawArticle]:
    """Fetch every daily page from start..end inclusive (oldest first)."""
    out: list[RawArticle] = []
    day = start
    # One shared client: connection reuse makes 180 daily pages fast.
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=TIMEOUT_S) as client:
        while day <= end:
            text = _fetch_wikitext(client, day)
            if text:
                out.extend(parse_day(text, day))
            time.sleep(REQUEST_DELAY_S)
            day += timedelta(days=1)
    return out


class CurrentEventsProvider(NewsProvider):
    name = "currentevents"

    def __init__(self, days: int = 3):
        self.days = max(1, days)

    def is_configured(self) -> bool:
        return True  # keyless public API

    def fetch_articles(self, query: str | None = None, limit: int = 500) -> list[RawArticle]:
        end = date.today()
        start = end - timedelta(days=self.days - 1)
        return fetch_range(start, end)[:limit]

    def fetch_history(self, days: int) -> list[RawArticle]:
        end = date.today()
        start = end - timedelta(days=max(1, days) - 1)
        return fetch_range(start, end)

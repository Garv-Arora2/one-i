"""Crux construction.

The crux is assembled from stored, verified event data with fixed templates.
No language model is involved: every sentence is either a slot filled from the
database or wording taken verbatim from a source article, and every part
records the article ids it came from.

When the underlying data is thin, the crux gets shorter rather than invented.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime

from app.analysis.entities import extract_entities
from app.analysis.numbers import NumberComparison
from app.analysis.textutils import truncate_words
from app.core.timeutil import as_utc
from app.models.enums import ValueKind

MAX_CRUX_WORDS = 200


@dataclass(frozen=True)
class CruxDevelopment:
    id: int | None
    title: str
    description: str
    occurred_at: datetime | None
    importance: float
    supporting_article_ids: list[int] = field(default_factory=list)


@dataclass(frozen=True)
class CruxArticle:
    id: int
    source_id: int
    source_name: str
    published_at: datetime | None


@dataclass(frozen=True)
class CruxPart:
    label: str
    text: str
    article_ids: list[int] = field(default_factory=list)


@dataclass
class CruxResult:
    text: str
    parts: list[CruxPart]
    context_text: str
    context_parts: list[CruxPart]

    def to_dict(self) -> dict:
        return {
            "parts": [part.__dict__ for part in self.parts],
            "context_parts": [part.__dict__ for part in self.context_parts],
        }


def format_value(value: float, value_kind: ValueKind, unit: str | None) -> str:
    if value_kind in {ValueKind.PERCENT, ValueKind.PERCENT_CHANGE}:
        return f"{value:g}%"
    if value_kind is ValueKind.PERCENTAGE_POINT:
        return f"{value:g} percentage points"
    if value_kind is ValueKind.CURRENCY:
        return f"{value:,.0f} {unit}" if unit else f"{value:,.0f}"
    formatted = f"{value:,.0f}" if float(value).is_integer() else f"{value:,.2f}"
    return f"{formatted} {unit}" if unit else formatted


def _format_date(value: datetime | None) -> str | None:
    normalized = as_utc(value)
    if normalized is None:
        return None
    return normalized.strftime("%d %B %Y").lstrip("0")


def _who(developments: list[CruxDevelopment], limit: int = 4) -> tuple[str, list[int]]:
    counts: Counter[str] = Counter()
    article_ids: list[int] = []
    for development in developments:
        counts.update(extract_entities(development.description))
        article_ids.extend(development.supporting_article_ids)
    names = [name for name, _ in counts.most_common(limit)]
    return ", ".join(names), sorted(set(article_ids))


def _number_sentence(comparison: NumberComparison) -> str:
    low = format_value(comparison.lowest, comparison.value_kind, comparison.unit)
    high = format_value(comparison.highest, comparison.value_kind, comparison.unit)
    subject = comparison.subject
    if comparison.sources_agree:
        return f"{high} {subject} ({comparison.distinct_source_count} sources report the same figure)"
    difference = format_value(comparison.difference, ValueKind.OTHER, comparison.difference_unit)
    return f"{subject}: reported between {low} and {high} (a difference of {difference})"


def build_crux(
    *,
    title: str,
    event_time: datetime | None,
    location: str | None,
    developments: list[CruxDevelopment],
    number_comparisons: list[NumberComparison],
    articles: list[CruxArticle],
) -> CruxResult:
    """Assemble the crux and the provenance context for one event."""
    parts: list[CruxPart] = []

    chronological = sorted(
        developments, key=lambda development: (as_utc(development.occurred_at) or _MIN_TIME)
    )
    by_importance = sorted(developments, key=lambda development: -development.importance)

    if by_importance:
        headline = by_importance[0]
        parts.append(
            CruxPart("What happened", headline.description, list(headline.supporting_article_ids))
        )
    else:
        parts.append(CruxPart("What happened", title, [article.id for article in articles]))

    who_text, who_articles = _who(by_importance[:4])
    if who_text:
        parts.append(CruxPart("Who is involved", who_text, who_articles))

    when_text = _format_date(event_time)
    if when_text:
        parts.append(
            CruxPart("When", when_text, [article.id for article in articles][:5])
        )
    if location:
        parts.append(CruxPart("Where", location, [article.id for article in articles][:5]))

    if len(chronological) > 1:
        listed = chronological[:3]
        parts.append(
            CruxPart(
                "Key developments",
                " ".join(f"{index + 1}. {truncate_words(item.title, 22)}" for index, item in enumerate(listed)),
                sorted({article_id for item in listed for article_id in item.supporting_article_ids}),
            )
        )

    reportable = number_comparisons[:3]
    if reportable:
        parts.append(
            CruxPart(
                "Reported numbers",
                "; ".join(_number_sentence(comparison) for comparison in reportable),
                sorted(
                    {
                        observation.article_id
                        for comparison in reportable
                        for observation in comparison.observations
                    }
                ),
            )
        )

    if chronological:
        latest = chronological[-1]
        parts.append(
            CruxPart("Latest reported step", latest.description, list(latest.supporting_article_ids))
        )

    text = _render(parts)
    context_parts = _build_context(articles, developments, number_comparisons)
    return CruxResult(
        text=text,
        parts=parts,
        context_text=" ".join(part.text for part in context_parts),
        context_parts=context_parts,
    )


def _render(parts: list[CruxPart]) -> str:
    """Join the parts into prose, trimming from the end to respect the cap."""
    rendered: list[str] = []
    words = 0
    for part in parts:
        sentence = part.text if part.text.endswith((".", "!", "?")) else f"{part.text}."
        if part.label not in {"What happened", "Latest reported step"}:
            sentence = f"{part.label}: {sentence}"
        sentence_words = len(sentence.split())
        if words + sentence_words > MAX_CRUX_WORDS and rendered:
            break
        rendered.append(sentence)
        words += sentence_words
    return " ".join(rendered)


def _build_context(
    articles: list[CruxArticle],
    developments: list[CruxDevelopment],
    number_comparisons: list[NumberComparison],
) -> list[CruxPart]:
    """Provenance, not background prose: where this account comes from."""
    parts: list[CruxPart] = []
    if not articles:
        return parts

    source_count = len({article.source_id for article in articles})
    times = [as_utc(article.published_at) for article in articles if article.published_at]
    span = ""
    if times:
        first, last = min(times), max(times)
        span = (
            f" published on {_format_date(first)}"
            if first.date() == last.date()
            else f" published between {_format_date(first)} and {_format_date(last)}"
        )
    parts.append(
        CruxPart(
            "Coverage",
            f"This account is drawn from {len(articles)} article"
            f"{'s' if len(articles) != 1 else ''} across {source_count} source"
            f"{'s' if source_count != 1 else ''}{span}.",
            [article.id for article in articles],
        )
    )

    if developments:
        parts.append(
            CruxPart(
                "Developments",
                f"{len(developments)} development"
                f"{'s' if len(developments) != 1 else ''} were identified from repeated reporting across sources.",
                sorted({aid for development in developments for aid in development.supporting_article_ids}),
            )
        )

    if number_comparisons:
        differing = [comparison for comparison in number_comparisons if not comparison.sources_agree]
        agreeing = len(number_comparisons) - len(differing)
        parts.append(
            CruxPart(
                "Figures",
                f"Sources report the same figure for {agreeing} claim"
                f"{'s' if agreeing != 1 else ''} and different figures for {len(differing)}.",
                sorted(
                    {
                        observation.article_id
                        for comparison in number_comparisons
                        for observation in comparison.observations
                    }
                ),
            )
        )
    return parts


_MIN_TIME = as_utc(datetime(1970, 1, 1))

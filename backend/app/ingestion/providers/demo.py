"""Demo providers.

They implement the same interfaces as the live providers and feed the same
ingestion pipeline, so the local demo exercises real code. Everything they
return is fictional and flagged with `is_demo=True`; demo rows are stored
separately from anything ingested from a real provider.
"""

from __future__ import annotations

import json
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from app.core.timeutil import parse_iso
from app.ingestion.providers.base import (
    MarketProvider,
    NewsProvider,
    RawArticle,
    RawPricePoint,
    RawReaction,
    ReactionProvider,
)

DATASET_PATH = Path(__file__).resolve().parents[2] / "seed" / "demo_dataset.json"
DEMO_PROVIDER_NAME = "demo"


@lru_cache
def load_demo_dataset(path: str | None = None) -> dict:
    dataset_path = Path(path) if path else DATASET_PATH
    with dataset_path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def demo_hints_by_url() -> dict[str, str]:
    """Maps each demo article URL to the event it belongs to.

    Used only to attach demo reactions and market data. Event grouping itself
    still runs the real algorithm over the demo articles.
    """
    dataset = load_demo_dataset()
    return {item["url"]: item["event_hint"] for item in dataset["articles"]}


class DemoNewsProvider(NewsProvider):
    name = DEMO_PROVIDER_NAME

    def is_configured(self) -> bool:
        return DATASET_PATH.exists()

    def configuration_hint(self) -> str:
        return "Built-in fictional sample articles."

    def fetch_articles(self, query: str | None = None, limit: int = 100) -> list[RawArticle]:
        dataset = load_demo_dataset()
        sources = {source["domain"]: source for source in dataset["sources"]}
        articles = [
            RawArticle(
                source_name=sources[item["source_domain"]]["name"],
                source_domain=item["source_domain"],
                source_type=sources[item["source_domain"]]["source_type"],
                title=item["title"],
                url=item["url"],
                content=item["content"],
                published_at=parse_iso(item["published_at"]),
                provider=DEMO_PROVIDER_NAME,
                is_demo=True,
            )
            for item in dataset["articles"]
        ]
        if query:
            needle = query.lower()
            articles = [
                article
                for article in articles
                if needle in article.title.lower() or needle in article.content.lower()
            ]
        return articles[:limit]


class DemoReactionProvider(ReactionProvider):
    name = DEMO_PROVIDER_NAME

    def is_configured(self) -> bool:
        return DATASET_PATH.exists()

    def configuration_hint(self) -> str:
        return "Built-in fictional sample discussion."

    def fetch_reactions(
        self,
        query: str,
        limit: int = 100,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        anchors: tuple[str, ...] = (),
    ) -> list[RawReaction]:
        _ = since, until, anchors
        return [
            reaction
            for reaction in self.fetch_all()
            if not query or query == reaction.provider or query in reaction.content.lower()
        ][:limit]

    def fetch_all(self) -> list[RawReaction]:
        dataset = load_demo_dataset()
        return [
            RawReaction(
                platform=item["platform"],
                external_id=item["external_id"],
                content=item["content"],
                published_at=parse_iso(item["published_at"]),
                engagement=int(item.get("engagement") or 0),
                url=item.get("url"),
                community=item.get("community"),
                provider=DEMO_PROVIDER_NAME,
                is_demo=True,
            )
            for item in dataset["reactions"]
        ]

    def fetch_all_with_hints(self) -> list[tuple[str, RawReaction]]:
        hints = [item["event_hint"] for item in load_demo_dataset()["reactions"]]
        return list(zip(hints, self.fetch_all(), strict=True))


class DemoMarketProvider(MarketProvider):
    name = DEMO_PROVIDER_NAME

    def is_configured(self) -> bool:
        return DATASET_PATH.exists()

    def configuration_hint(self) -> str:
        return "Built-in fictional sample price series."

    def fetch_prices(self, symbol: str, days: int = 30) -> list[RawPricePoint]:
        points = [point for point in self.fetch_all() if point.symbol == symbol]
        return points[-days:]

    def fetch_all(self) -> list[RawPricePoint]:
        return [point for _, point in self.fetch_all_with_hints()]

    def fetch_all_with_hints(self) -> list[tuple[str, RawPricePoint]]:
        dataset = load_demo_dataset()
        points: list[tuple[str, RawPricePoint]] = []
        for series in dataset["market"]:
            for point in series["points"]:
                timestamp = parse_iso(point["timestamp"])
                if timestamp is None:
                    continue
                points.append(
                    (
                        series["event_hint"],
                        RawPricePoint(
                            symbol=series["symbol"],
                            name=series.get("name"),
                            is_benchmark=bool(series.get("is_benchmark")),
                            timestamp=timestamp,
                            price=float(point["price"]),
                            volume=None if point.get("volume") is None else float(point["volume"]),
                            provider=DEMO_PROVIDER_NAME,
                            is_demo=True,
                        ),
                    )
                )
        return points

"""Provider interfaces and the raw payloads they return.

A provider is the only place that talks to an external service. Each one
reports whether it is configured; an unconfigured provider yields nothing
instead of inventing data.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


class ProviderError(RuntimeError):
    """Recoverable failure while talking to an external service."""


@dataclass(frozen=True)
class RawArticle:
    source_name: str
    source_domain: str
    title: str
    url: str
    content: str
    published_at: datetime | None
    provider: str
    source_type: str = "news_outlet"
    is_demo: bool = False


@dataclass(frozen=True)
class RawReaction:
    platform: str
    external_id: str
    content: str
    published_at: datetime | None
    engagement: int
    url: str | None
    community: str | None
    provider: str
    is_demo: bool = False


@dataclass(frozen=True)
class RawPricePoint:
    symbol: str
    timestamp: datetime
    price: float
    volume: float | None
    name: str | None = None
    is_benchmark: bool = False
    provider: str = "unknown"
    is_demo: bool = False


@dataclass
class ProviderStatus:
    name: str
    kind: str
    configured: bool
    detail: str


class BaseProvider(ABC):
    name: str = "base"
    kind: str = "generic"

    @abstractmethod
    def is_configured(self) -> bool: ...

    def status(self) -> ProviderStatus:
        return ProviderStatus(
            name=self.name,
            kind=self.kind,
            configured=self.is_configured(),
            detail=self.configuration_hint(),
        )

    def configuration_hint(self) -> str:
        return "Configured." if self.is_configured() else "Not configured."


class NewsProvider(BaseProvider):
    kind = "news"

    @abstractmethod
    def fetch_articles(self, query: str | None = None, limit: int = 50) -> list[RawArticle]: ...


class ReactionProvider(BaseProvider):
    kind = "reaction"

    @abstractmethod
    def fetch_reactions(
        self,
        query: str,
        limit: int = 50,
        *,
        since: datetime | None = None,
        until: datetime | None = None,
        anchors: tuple[str, ...] = (),
    ) -> list[RawReaction]:
        """``anchors``: when given, a result must mention at least one of them."""
        ...


class MarketProvider(BaseProvider):
    kind = "market"

    @abstractmethod
    def fetch_prices(self, symbol: str, days: int = 30) -> list[RawPricePoint]: ...


@dataclass
class IngestionReport:
    """What one ingestion run actually did."""

    fetched: int = 0
    invalid: int = 0
    duplicates: int = 0
    stored: int = 0
    already_present: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "IngestionReport") -> "IngestionReport":
        return IngestionReport(
            fetched=self.fetched + other.fetched,
            invalid=self.invalid + other.invalid,
            duplicates=self.duplicates + other.duplicates,
            stored=self.stored + other.stored,
            already_present=self.already_present + other.already_present,
            errors=[*self.errors, *other.errors],
        )

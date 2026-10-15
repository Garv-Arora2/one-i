"""Provider registry.

Builds the set of live providers from environment configuration and reports
which ones are usable. Demo providers are never mixed into the live set.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.config import Settings, get_settings
from app.ingestion.providers.base import (
    MarketProvider,
    NewsProvider,
    ProviderStatus,
    ReactionProvider,
)
from app.ingestion.providers.currentevents import CurrentEventsProvider
from app.ingestion.providers.gdelt import GdeltNewsProvider
from app.ingestion.providers.market import AlphaVantageProvider
from app.ingestion.providers.newsapi import NewsApiProvider
from app.ingestion.providers.reddit import RedditProvider
from app.ingestion.providers.rss import RssNewsProvider
from app.ingestion.providers.youtube import YouTubeProvider


@dataclass
class ProviderRegistry:
    news: list[NewsProvider] = field(default_factory=list)
    reactions: list[ReactionProvider] = field(default_factory=list)
    market: list[MarketProvider] = field(default_factory=list)

    def configured_news(self) -> list[NewsProvider]:
        return [provider for provider in self.news if provider.is_configured()]

    def configured_reactions(self) -> list[ReactionProvider]:
        return [provider for provider in self.reactions if provider.is_configured()]

    def configured_market(self) -> list[MarketProvider]:
        return [provider for provider in self.market if provider.is_configured()]

    def statuses(self) -> list[ProviderStatus]:
        return [
            provider.status()
            for provider in [*self.news, *self.reactions, *self.market]
        ]

    @property
    def any_configured(self) -> bool:
        return bool(self.configured_news() or self.configured_reactions() or self.configured_market())


def build_registry(settings: Settings | None = None) -> ProviderRegistry:
    settings = settings or get_settings()
    timeout = settings.http_timeout_seconds
    return ProviderRegistry(
        news=[
            RssNewsProvider(settings.rss_feed_list, timeout),
            GdeltNewsProvider(
                settings.gdelt_enabled,
                settings.gdelt_query_list or None,
                settings.gdelt_timespan,
                settings.gdelt_max_records,
                timeout,
            ),
            NewsApiProvider(settings.news_api_key, settings.news_api_base_url, timeout),
            CurrentEventsProvider(settings.current_events_days),
        ],
        reactions=[
            RedditProvider(
                settings.reddit_client_id,
                settings.reddit_client_secret,
                settings.reddit_user_agent,
                timeout,
            ),
            YouTubeProvider(settings.youtube_api_key, timeout),
        ],
        market=[
            AlphaVantageProvider(settings.market_api_key, settings.market_api_base_url, timeout)
        ],
    )

"""Application configuration.

All secrets and deployment-specific values come from environment variables.
Nothing here contains a real credential.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.ingestion.default_feeds import parse_rss_feeds

Environment = Literal["development", "test", "production"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    environment: Environment = "development"
    app_name: str = "ONE I"

    # PostgreSQL is the target database. When DATABASE_URL is not configured the
    # application falls back to a local SQLite file so the product remains
    # runnable on a machine without a database server. See docs/architecture.md.
    database_url: str = "sqlite+pysqlite:///./one_i.db"
    database_echo: bool = False

    cors_origins: str = "http://localhost:3000"

    # --- Ingestion providers -------------------------------------------------
    # Empty values mean "provider not configured"; the ingestion registry then
    # reports the provider as unavailable instead of inventing data.
    news_api_key: str = ""
    news_api_base_url: str = "https://newsapi.org/v2"
    # Empty means use the default public outlet list. Set to "off" to disable.
    rss_feeds: str = ""
    # Keyless global news inlet (GDELT DOC 2.1). Enabled by default; set
    # GDELT_ENABLED=false to turn it off. GDELT_QUERIES is a comma-separated
    # list of search terms; empty means a built-in set of broad world-news
    # queries. GDELT_TIMESPAN is the rolling window for routine ingest
    # (e.g. "7d"); backfill walks further back week by week instead.
    gdelt_enabled: bool = True
    gdelt_queries: str = ""
    gdelt_timespan: str = "7d"
    gdelt_max_records: int = 100
    # Keyless Wikipedia current-events inlet. Routine ingest pulls this many
    # recent days; --history-days reaches further back for the 6-month sweep.
    current_events_days: int = 3
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "one-i/1.0"
    youtube_api_key: str = ""
    market_api_key: str = ""
    market_api_base_url: str = "https://www.alphavantage.co/query"
    http_timeout_seconds: float = 15.0

    # --- Authentication ------------------------------------------------------
    google_client_id: str = ""
    session_secret: str = "dev-only-insecure-secret-change-me"
    session_cookie_name: str = "one_i_session"
    session_ttl_hours: int = 24
    captcha_provider: Literal["turnstile", "recaptcha", "none"] = "none"
    captcha_secret_key: str = ""
    captcha_verify_url_turnstile: str = (
        "https://challenges.cloudflare.com/turnstile/v0/siteverify"
    )
    captcha_verify_url_recaptcha: str = "https://www.google.com/recaptcha/api/siteverify"
    # Local convenience only. Refused when environment == "production".
    auth_dev_bypass: bool = False

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def rss_feed_list(self) -> list[str]:
        return parse_rss_feeds(self.rss_feeds)

    @property
    def gdelt_query_list(self) -> list[str]:
        return [query.strip() for query in self.gdelt_queries.split(",") if query.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def google_auth_configured(self) -> bool:
        return bool(self.google_client_id)

    @property
    def captcha_configured(self) -> bool:
        return self.captcha_provider != "none" and bool(self.captcha_secret_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()

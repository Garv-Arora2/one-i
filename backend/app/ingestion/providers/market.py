"""Market data provider (Alpha Vantage daily series)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

import httpx

from app.ingestion.providers.base import MarketProvider, ProviderError, RawPricePoint

logger = logging.getLogger(__name__)


class AlphaVantageProvider(MarketProvider):
    name = "alphavantage"

    def __init__(self, api_key: str, base_url: str, timeout: float = 15.0) -> None:
        self._api_key = api_key
        self._base_url = base_url
        self._timeout = timeout

    def is_configured(self) -> bool:
        return bool(self._api_key)

    def configuration_hint(self) -> str:
        return (
            "Configured."
            if self.is_configured()
            else "Set MARKET_API_KEY to enable market data."
        )

    def fetch_prices(self, symbol: str, days: int = 30) -> list[RawPricePoint]:
        if not self.is_configured():
            return []
        try:
            with httpx.Client(timeout=self._timeout) as client:
                response = client.get(
                    self._base_url,
                    params={
                        "function": "TIME_SERIES_DAILY",
                        "symbol": symbol,
                        "outputsize": "compact",
                        "apikey": self._api_key,
                    },
                )
        except httpx.HTTPError as error:
            raise ProviderError(f"Market data request failed: {error}") from error

        if response.status_code >= 400:
            raise ProviderError(f"Market data provider returned HTTP {response.status_code}.")
        return parse_alpha_vantage_payload(response.json(), symbol)[:days]


def parse_alpha_vantage_payload(payload: dict, symbol: str) -> list[RawPricePoint]:
    """Map a daily time series payload to price points, newest last."""
    if not isinstance(payload, dict):
        raise ProviderError("Market data provider returned an unexpected payload.")
    if "Note" in payload or "Information" in payload:
        raise ProviderError("Market data provider rate limit reached.")
    if "Error Message" in payload:
        raise ProviderError(f"Market data provider error: {payload['Error Message']}")

    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict):
        raise ProviderError("Market data payload did not contain a daily time series.")

    points: list[RawPricePoint] = []
    for day, values in series.items():
        try:
            timestamp = datetime.strptime(day, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            close = float(values["4. close"])
        except (ValueError, KeyError, TypeError):
            logger.warning("Skipping malformed market row for %s on %s", symbol, day)
            continue
        volume_raw = values.get("5. volume")
        points.append(
            RawPricePoint(
                symbol=symbol,
                timestamp=timestamp,
                price=close,
                volume=float(volume_raw) if volume_raw not in (None, "") else None,
                provider="alphavantage",
            )
        )
    points.sort(key=lambda point: point.timestamp)
    return points

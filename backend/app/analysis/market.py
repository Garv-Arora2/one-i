"""Market impact calculations.

Only descriptive arithmetic over a window that is fixed in advance
(`thresholds.MarketConfig`), never chosen after seeing the outcome. The output
describes what the price did during the window; it never claims the event
caused it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

import pandas as pd

from app.analysis.thresholds import MARKET, MarketConfig
from app.core.timeutil import as_utc


@dataclass(frozen=True)
class PricePoint:
    timestamp: datetime
    price: float
    volume: float | None = None


@dataclass
class MarketImpact:
    available: bool
    unavailable_reason: str | None = None
    symbol: str | None = None
    name: str | None = None
    window_start: datetime | None = None
    window_end: datetime | None = None
    start_price: float | None = None
    end_price: float | None = None
    return_percent: float | None = None
    benchmark_symbol: str | None = None
    benchmark_return_percent: float | None = None
    difference_percentage_points: float | None = None
    baseline_average_volume: float | None = None
    window_average_volume: float | None = None
    volume_change_percent: float | None = None
    series: list[dict] = field(default_factory=list)
    benchmark_series: list[dict] = field(default_factory=list)


def _frame(points: list[PricePoint]) -> pd.DataFrame:
    rows = [
        {
            "timestamp": as_utc(point.timestamp),
            "price": float(point.price),
            "volume": float(point.volume) if point.volume is not None else float("nan"),
        }
        for point in points
        if point.timestamp is not None
    ]
    frame = pd.DataFrame(rows, columns=["timestamp", "price", "volume"])
    if frame.empty:
        return frame
    return frame.sort_values("timestamp").reset_index(drop=True)


def simple_return(start_price: float, end_price: float) -> float:
    """(end - start) / start * 100."""
    if start_price == 0:
        raise ValueError("start_price must be non-zero")
    return round((end_price - start_price) / start_price * 100, 4)


def _window_slice(frame: pd.DataFrame, start: datetime, end: datetime) -> pd.DataFrame:
    return frame[(frame["timestamp"] >= start) & (frame["timestamp"] <= end)]


def _series_payload(frame: pd.DataFrame) -> list[dict]:
    return [
        {
            "timestamp": row.timestamp.isoformat(),
            "price": round(float(row.price), 4),
            "volume": None if pd.isna(row.volume) else float(row.volume),
        }
        for row in frame.itertuples()
    ]


def compute_market_impact(
    *,
    symbol: str,
    name: str | None,
    security_points: list[PricePoint],
    event_time: datetime | None,
    benchmark_symbol: str | None = None,
    benchmark_points: list[PricePoint] | None = None,
    config: MarketConfig = MARKET,
) -> MarketImpact:
    """Describe the security's movement over the predefined event window."""
    if event_time is None:
        return MarketImpact(
            available=False,
            unavailable_reason="The event time is not precise enough to select a market window.",
        )

    frame = _frame(security_points)
    if len(frame) < config.min_points_required:
        return MarketImpact(
            available=False,
            unavailable_reason="Not enough market data has been collected for this event.",
        )

    anchor = as_utc(event_time)
    window_end = anchor + timedelta(days=config.window_days)
    baseline_start = anchor - timedelta(days=config.baseline_days)

    before = frame[frame["timestamp"] <= anchor]
    # The last close before the event is the reference price.
    start_row = before.iloc[-1] if not before.empty else frame.iloc[0]
    window = _window_slice(frame, start_row["timestamp"], window_end)
    if len(window) < config.min_points_required:
        return MarketImpact(
            available=False,
            unavailable_reason="Not enough market data inside the event window.",
        )
    end_row = window.iloc[-1]

    baseline = _window_slice(frame, baseline_start, anchor)
    baseline_volume = float(baseline["volume"].mean()) if not baseline.empty else float("nan")
    window_volume = float(window["volume"].mean()) if not window.empty else float("nan")
    volume_change = None
    if pd.notna(baseline_volume) and pd.notna(window_volume) and baseline_volume > 0:
        volume_change = round((window_volume - baseline_volume) / baseline_volume * 100, 2)

    security_return = simple_return(float(start_row["price"]), float(end_row["price"]))

    benchmark_return = None
    difference = None
    benchmark_payload: list[dict] = []
    if benchmark_points:
        benchmark_frame = _frame(benchmark_points)
        benchmark_window = _window_slice(benchmark_frame, start_row["timestamp"], window_end)
        if len(benchmark_window) >= config.min_points_required:
            benchmark_return = simple_return(
                float(benchmark_window.iloc[0]["price"]), float(benchmark_window.iloc[-1]["price"])
            )
            difference = round(security_return - benchmark_return, 4)
        benchmark_payload = _series_payload(benchmark_frame)

    return MarketImpact(
        available=True,
        symbol=symbol,
        name=name,
        window_start=start_row["timestamp"].to_pydatetime(),
        window_end=end_row["timestamp"].to_pydatetime(),
        start_price=round(float(start_row["price"]), 4),
        end_price=round(float(end_row["price"]), 4),
        return_percent=security_return,
        benchmark_symbol=benchmark_symbol,
        benchmark_return_percent=benchmark_return,
        difference_percentage_points=difference,
        baseline_average_volume=None if pd.isna(baseline_volume) else round(baseline_volume, 2),
        window_average_volume=None if pd.isna(window_volume) else round(window_volume, 2),
        volume_change_percent=volume_change,
        series=_series_payload(frame),
        benchmark_series=benchmark_payload,
    )

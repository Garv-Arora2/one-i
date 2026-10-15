from datetime import datetime, timedelta, timezone

import pytest

from app.analysis.market import PricePoint, compute_market_impact, simple_return

EVENT_TIME = datetime(2026, 3, 3, 5, 10, tzinfo=timezone.utc)


# Daily closes on the trading days around the event (24 Feb 2026 is a Tuesday,
# so 28 Feb and 1 Mar are skipped as a weekend).
TRADING_DAYS = [
    datetime(2026, 2, 24, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 2, 25, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 2, 26, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 2, 27, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 2, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 3, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 4, 21, 0, tzinfo=timezone.utc),
    datetime(2026, 3, 5, 21, 0, tzinfo=timezone.utc),
]


def series(prices: list[float], volumes: list[float] | None = None) -> list[PricePoint]:
    return [
        PricePoint(
            timestamp=TRADING_DAYS[index],
            price=price,
            volume=volumes[index] if volumes else None,
        )
        for index, price in enumerate(prices)
    ]


def test_simple_return_matches_the_documented_formula():
    assert simple_return(50.0, 45.0) == -10.0


def test_simple_return_rejects_zero_start():
    with pytest.raises(ValueError):
        simple_return(0.0, 10.0)


def test_return_is_measured_from_the_last_price_before_the_event():
    prices = [48.1, 48.35, 47.9, 48.6, 48.75, 45.73, 45.62, 45.95]
    impact = compute_market_impact(
        symbol="VNTR", name="Vantor Industries", security_points=series(prices), event_time=EVENT_TIME
    )
    assert impact.available is True
    assert impact.start_price == 48.75
    assert impact.return_percent == pytest.approx(-6.42, abs=0.01)


def test_benchmark_difference_is_reported_in_percentage_points():
    prices = [48.1, 48.35, 47.9, 48.6, 48.75, 45.73, 45.62, 45.95]
    benchmark = [4120.5, 4132.0, 4118.7, 4140.2, 4155.8, 4148.3, 4160.9, 4172.4]
    impact = compute_market_impact(
        symbol="VNTR",
        name="Vantor Industries",
        security_points=series(prices),
        event_time=EVENT_TIME,
        benchmark_symbol="MRDX",
        benchmark_points=series(benchmark),
    )
    assert impact.benchmark_return_percent == pytest.approx(0.12, abs=0.01)
    assert impact.difference_percentage_points == pytest.approx(
        impact.return_percent - impact.benchmark_return_percent, abs=0.001
    )


def test_volume_change_uses_the_predefined_baseline():
    prices = [48.1, 48.35, 47.9, 48.6, 48.75, 45.73, 45.62, 45.95]
    volumes = [1.2e6, 1.1e6, 1.3e6, 1.0e6, 1.15e6, 4.6e6, 3.2e6, 2.1e6]
    impact = compute_market_impact(
        symbol="VNTR",
        name="Vantor Industries",
        security_points=series(prices, volumes),
        event_time=EVENT_TIME,
    )
    assert impact.baseline_average_volume == pytest.approx(1_150_000, rel=0.01)
    assert impact.volume_change_percent > 100


def test_missing_event_time_makes_market_impact_unavailable():
    impact = compute_market_impact(
        symbol="VNTR", name=None, security_points=series([48.0, 47.0]), event_time=None
    )
    assert impact.available is False
    assert "event time" in impact.unavailable_reason.lower()


def test_too_few_points_makes_market_impact_unavailable():
    impact = compute_market_impact(
        symbol="VNTR", name=None, security_points=series([48.0]), event_time=EVENT_TIME
    )
    assert impact.available is False


def test_window_is_fixed_in_advance_and_reported():
    prices = [48.1, 48.35, 47.9, 48.6, 48.75, 45.73, 45.62, 45.95]
    impact = compute_market_impact(
        symbol="VNTR", name=None, security_points=series(prices), event_time=EVENT_TIME
    )
    assert impact.window_start == TRADING_DAYS[4]
    assert impact.window_end == TRADING_DAYS[6]


def test_no_data_at_all_is_reported_as_unavailable():
    impact = compute_market_impact(
        symbol="VNTR", name=None, security_points=[], event_time=EVENT_TIME
    )
    assert impact.available is False
    assert impact.return_percent is None

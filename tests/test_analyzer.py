"""Tests for analysis routines."""

from datetime import datetime, timedelta

from rate_monitor.analyzer import RateStats, analyze_history


def _series(values: list[float]) -> list[tuple[datetime, float]]:
    base = datetime(2024, 1, 1)
    return [(base + timedelta(minutes=i), v) for i, v in enumerate(values)]


def test_increasing_series_triggers_alert_on_short_window() -> None:
    history = _series([10, 11, 12, 13, 14])

    stats = analyze_history(history, window_short=3, window_long=5, threshold_percent=5.0, target_id="btc")

    assert isinstance(stats, RateStats)
    assert stats.current == 14
    assert stats.short_avg == (12 + 13 + 14) / 3
    assert stats.should_alert is True
    assert stats.reason and "short average" in stats.reason.lower()


def test_small_changes_do_not_trigger_alert() -> None:
    history = _series([100, 100.5, 101.0])

    stats = analyze_history(history, window_short=3, window_long=3, threshold_percent=5.0, target_id="eth")

    assert stats.should_alert is False
    assert stats.reason is None


def test_large_change_triggers_alert() -> None:
    history = _series([100, 100, 80])

    stats = analyze_history(history, window_short=2, window_long=3, threshold_percent=10.0, target_id="xrp")

    assert stats.should_alert is True
    assert stats.reason is not None
    assert stats.change_from_short_pct is not None
    assert stats.change_from_short_pct < 0


def test_insufficient_history_returns_partial_stats() -> None:
    history = _series([50, 60])

    stats = analyze_history(history, window_short=3, window_long=5, threshold_percent=5.0, target_id="ltc")

    assert stats.current == 60
    assert stats.short_avg is None
    assert stats.long_avg is None
    assert stats.change_from_short_pct is None
    assert stats.change_from_long_pct is None
    assert stats.should_alert is False

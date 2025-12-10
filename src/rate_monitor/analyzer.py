"""Analysis routines for rate data."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import List, Optional, Tuple


@dataclass
class RateStats:
    """Aggregated statistics for a target's rate history."""

    target_id: str
    current: float | None
    short_avg: float | None
    long_avg: float | None
    change_from_short_pct: float | None
    change_from_long_pct: float | None
    should_alert: bool
    reason: str | None


def _average_tail(values: List[Tuple[datetime, float]], window: int) -> Optional[float]:
    if len(values) < window:
        return None
    tail = [value for _, value in values[-window:]]
    return mean(tail)


def _pct_change(current: float, base: Optional[float]) -> Optional[float]:
    if base is None or base == 0:
        return None
    return (current - base) / base * 100


def analyze_history(
    values: List[Tuple[datetime, float]],
    window_short: int,
    window_long: int,
    threshold_percent: float,
    target_id: str,
) -> RateStats:
    """Analyze historical values and decide whether to raise an alert."""
    if not values:
        return RateStats(
            target_id=target_id,
            current=None,
            short_avg=None,
            long_avg=None,
            change_from_short_pct=None,
            change_from_long_pct=None,
            should_alert=False,
            reason=None,
        )

    current = values[-1][1]
    short_avg = _average_tail(values, window_short)
    long_avg = _average_tail(values, window_long)

    change_short = _pct_change(current, short_avg)
    change_long = _pct_change(current, long_avg)

    should_alert = False
    reason: Optional[str] = None

    if change_short is not None and abs(change_short) > threshold_percent:
        should_alert = True
        reason = f"Change from short average exceeded {threshold_percent}%"
    elif change_long is not None and abs(change_long) > threshold_percent:
        should_alert = True
        reason = f"Change from long average exceeded {threshold_percent}%"

    return RateStats(
        target_id=target_id,
        current=current,
        short_avg=short_avg,
        long_avg=long_avg,
        change_from_short_pct=change_short,
        change_from_long_pct=change_long,
        should_alert=should_alert,
        reason=reason,
    )

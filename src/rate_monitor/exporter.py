"""Export utilities for processed rate data."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path
from typing import Iterable, Tuple

from rate_monitor.analyzer import RateStats


def _prepare_path(path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    return destination


def export_history_to_csv(rows: Iterable[Tuple[str, str, float]], path: str | Path) -> None:
    """Export rate history rows to a CSV file."""
    destination = _prepare_path(path)
    with destination.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["timestamp", "target_id", "value"])
        for ts_iso, target_id, value in rows:
            writer.writerow([ts_iso, target_id, value])


def export_stats_to_json(stats_list: Iterable[RateStats], path: str | Path) -> None:
    """Export aggregated statistics to a JSON file."""
    destination = _prepare_path(path)
    data = [asdict(stats) for stats in stats_list]
    with destination.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

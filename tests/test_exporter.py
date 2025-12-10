"""Tests for exporter utilities."""

import json
from pathlib import Path

from rate_monitor.analyzer import RateStats
from rate_monitor.exporter import export_history_to_csv, export_stats_to_json


def test_export_history_to_csv(tmp_path: Path) -> None:
    output = tmp_path / "history.csv"
    rows = [
        ("2025-01-01T00:00:00Z", "btc", 100.0),
        ("2025-01-01T01:00:00Z", "eth", 200.5),
    ]

    export_history_to_csv(rows, output)

    content = output.read_text(encoding="utf-8").splitlines()
    assert content[0] == "timestamp,target_id,value"
    assert content[1] == "2025-01-01T00:00:00Z,btc,100.0"
    assert content[2] == "2025-01-01T01:00:00Z,eth,200.5"


def test_export_stats_to_json(tmp_path: Path) -> None:
    output = tmp_path / "stats.json"
    stats = [
        RateStats(
            target_id="btc",
            current=100.0,
            short_avg=95.0,
            long_avg=90.0,
            change_from_short_pct=5.26,
            change_from_long_pct=11.11,
            should_alert=True,
            reason="Change from short average exceeded 5%",
        ),
        RateStats(
            target_id="eth",
            current=None,
            short_avg=None,
            long_avg=None,
            change_from_short_pct=None,
            change_from_long_pct=None,
            should_alert=False,
            reason=None,
        ),
    ]

    export_stats_to_json(stats, output)

    data = json.loads(output.read_text(encoding="utf-8"))
    assert data[0]["target_id"] == "btc"
    assert data[0]["current"] == 100.0
    assert data[0]["should_alert"] is True
    assert data[1]["target_id"] == "eth"
    assert data[1]["should_alert"] is False

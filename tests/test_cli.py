"""Smoke tests for CLI argument parsing and dry-run flow."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List

import pytest

from rate_monitor import cli
from rate_monitor.analyzer import RateStats
from rate_monitor.config import TargetConfig


def test_cli_dry_run_skips_db_inserts(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    inserted: List[Any] = []
    exported_history: List[Any] = []
    exported_stats: List[Any] = []
    notified: List[RateStats] = []

    class DummyDB:
        def __init__(self, path: str) -> None:
            self.path = path

        def init_schema(self) -> None:
            pass

        def insert_rate(self, *args: Any, **kwargs: Any) -> None:
            inserted.append((args, kwargs))

        def get_history(self, *args: Any, **kwargs: Any):
            return []

    class DummyFetcher:
        def get(self, url: str) -> str:
            return "<div>dummy</div>"

    class DummyParser:
        def __init__(self, selector: str) -> None:
            self.selector = selector

        def parse(self, html: str) -> float:
            return 123.45

    class DummyNotifier:
        def notify(self, stats: RateStats) -> None:
            notified.append(stats)

    def fake_load_settings(path: str) -> Any:
        return SimpleNamespace(
            db=SimpleNamespace(path=str(tmp_path / "rates.db")),
            alerts=SimpleNamespace(threshold=5.0),
            slack=SimpleNamespace(enabled=False, webhook_url=""),
        )

    def fake_load_targets(path: str) -> Any:
        return [TargetConfig(id="t1", name="Test", url="https://example.com", selector=".value")]

    def fake_analyze_history(**kwargs: Any) -> RateStats:
        return RateStats(
            target_id=kwargs["target_id"],
            current=kwargs["values"][-1][1] if kwargs["values"] else None,
            short_avg=None,
            long_avg=None,
            change_from_short_pct=None,
            change_from_long_pct=None,
            should_alert=False,
            reason=None,
        )

    def fake_export_history(rows, path):
        exported_history.append((list(rows), path))

    def fake_export_stats(stats, path):
        exported_stats.append((list(stats), path))

    monkeypatch.setattr(cli, "RateDatabase", DummyDB)
    monkeypatch.setattr(cli, "Fetcher", DummyFetcher)
    monkeypatch.setattr(cli, "RatePageParser", DummyParser)
    monkeypatch.setattr(cli, "StdoutNotifier", DummyNotifier)
    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    monkeypatch.setattr(cli, "load_targets", fake_load_targets)
    monkeypatch.setattr(cli, "analyze_history", fake_analyze_history)
    monkeypatch.setattr(cli, "export_history_to_csv", fake_export_history)
    monkeypatch.setattr(cli, "export_stats_to_json", fake_export_stats)

    cli.main(["--dry-run", "--output-dir", str(tmp_path)])

    assert inserted == []  # no DB writes
    assert len(exported_history) == 1
    assert len(exported_stats) == 1
    assert len(notified) == 1  # notifier invoked for target

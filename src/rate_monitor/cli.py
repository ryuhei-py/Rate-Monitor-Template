"""Command-line interface for the rate monitor."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple

from rate_monitor.analyzer import RateStats, analyze_history
from rate_monitor.config import load_settings, load_targets
from rate_monitor.db import RateDatabase
from rate_monitor.exporter import export_history_to_csv, export_stats_to_json
from rate_monitor.fetcher import Fetcher
from rate_monitor.notifier import SlackNotifier, StdoutNotifier
from rate_monitor.parser import RatePageParser


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch and analyze rate data.")
    parser.add_argument("--targets", default="config/targets.example.yml", help="Path to targets YAML.")
    parser.add_argument("--settings", default="config/settings.example.yml", help="Path to settings YAML.")
    parser.add_argument("--output-dir", default="sample_output", help="Directory for exported outputs.")
    parser.add_argument("--dry-run", action="store_true", help="Run without persisting data.")
    return parser


def _select_notifier(settings: any) -> any:
    if getattr(settings.slack, "enabled", False) and getattr(settings.slack, "webhook_url", None):
        return SlackNotifier(settings.slack.webhook_url)
    return StdoutNotifier()


def main(argv: List[str] | None = None) -> None:
    args = _build_parser().parse_args(argv)
    try:
        settings = load_settings(args.settings)
        targets = load_targets(args.targets)

        db = RateDatabase(settings.db.path)
        db.init_schema()

        fetcher = Fetcher()
        notifier = _select_notifier(settings)

        window_short = 3
        window_long = 7
        threshold = settings.alerts.threshold or 0.0

        history_rows: List[Tuple[str, str, float]] = []
        stats_list: List[RateStats] = []

        for target in targets:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            html = fetcher.get(target.url)
            parser = RatePageParser(target.selector)
            rate = parser.parse(html)

            if not args.dry_run:
                db.insert_rate(target.id, now, rate)

            history = db.get_history(target.id, days=window_long)
            if args.dry_run:
                history = history + [(now, rate)]

            stats = analyze_history(
                values=history,
                window_short=window_short,
                window_long=window_long,
                threshold_percent=threshold,
                target_id=target.id,
            )
            stats_list.append(stats)
            notifier.notify(stats)

            history_rows.append((now.isoformat(), target.id, rate))

        output_dir = Path(args.output_dir)
        export_history_to_csv(history_rows, output_dir / "rates.csv")
        export_stats_to_json(stats_list, output_dir / "latest_stats.json")
    except Exception as exc:  # noqa: BLE001
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()

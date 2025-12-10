"""Notification handlers for alerts."""

from __future__ import annotations

import sys
from typing import Protocol, TextIO

import requests

from rate_monitor.analyzer import RateStats


class NotificationError(RuntimeError):
    """Raised when sending a notification fails."""


class Notifier(Protocol):
    """Notifier interface."""

    def notify(self, stats: RateStats) -> None: ...


class StdoutNotifier:
    """Notifier that writes alert summaries to stdout."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream or sys.stdout

    def notify(self, stats: RateStats) -> None:
        if not stats.should_alert:
            return

        parts = [f"[ALERT] {stats.target_id}"]
        if stats.current is not None:
            parts.append(f"current={stats.current}")
        if stats.change_from_short_pct is not None:
            parts.append(f"change_from_short={stats.change_from_short_pct:+.1f}%")
        if stats.change_from_long_pct is not None:
            parts.append(f"change_from_long={stats.change_from_long_pct:+.1f}%")
        if stats.reason:
            parts.append(f"reason={stats.reason}")

        message = " ".join(parts)
        print(message, file=self.stream)


class SlackNotifier:
    """Notifier that posts alert summaries to a Slack webhook."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url

    def notify(self, stats: RateStats) -> None:
        if not stats.should_alert:
            return

        text_parts = [f"[ALERT] {stats.target_id}"]
        if stats.current is not None:
            text_parts.append(f"current={stats.current}")
        if stats.change_from_short_pct is not None:
            text_parts.append(f"Δshort={stats.change_from_short_pct:+.1f}%")
        if stats.change_from_long_pct is not None:
            text_parts.append(f"Δlong={stats.change_from_long_pct:+.1f}%")
        if stats.reason:
            text_parts.append(stats.reason)

        payload = {"text": " ".join(text_parts)}

        try:
            response = requests.post(self.webhook_url, json=payload, timeout=5)
            response.raise_for_status()
        except requests.exceptions.RequestException as exc:
            raise NotificationError(f"Failed to send Slack notification: {exc}") from exc

"""Tests for notifier handlers."""

from __future__ import annotations

import io
from types import SimpleNamespace
from typing import Any, List

import pytest
import requests

from rate_monitor.analyzer import RateStats
from rate_monitor.notifier import NotificationError, SlackNotifier, StdoutNotifier


def _stats(should_alert: bool = True, **overrides: Any) -> RateStats:
    base = RateStats(
        target_id="usd_jpy",
        current=150.0,
        short_avg=140.0,
        long_avg=135.0,
        change_from_short_pct=7.1,
        change_from_long_pct=11.1,
        should_alert=should_alert,
        reason="Change from short average exceeded threshold",
    )
    return base if not overrides else base.__class__(**{**base.__dict__, **overrides})


def test_stdout_notifier_prints_when_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    buffer = io.StringIO()
    notifier = StdoutNotifier(stream=buffer)

    notifier.notify(_stats())

    output = buffer.getvalue().strip()
    assert output.startswith("[ALERT] usd_jpy")
    assert "current=150.0" in output


def test_stdout_notifier_skips_when_no_alert() -> None:
    buffer = io.StringIO()
    notifier = StdoutNotifier(stream=buffer)

    notifier.notify(_stats(should_alert=False))

    assert buffer.getvalue() == ""


def test_slack_notifier_not_called_when_no_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    called: List[Any] = []

    def fake_post(*args: Any, **kwargs: Any) -> Any:
        called.append((args, kwargs))
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None)

    monkeypatch.setattr(requests, "post", fake_post)
    notifier = SlackNotifier("https://hooks.slack.com/fake")

    notifier.notify(_stats(should_alert=False))

    assert called == []


def test_slack_notifier_posts_on_alert(monkeypatch: pytest.MonkeyPatch) -> None:
    called: List[Any] = []

    def fake_post(url: str, **kwargs: Any) -> Any:
        called.append((url, kwargs))
        return SimpleNamespace(status_code=200, raise_for_status=lambda: None)

    monkeypatch.setattr(requests, "post", fake_post)
    notifier = SlackNotifier("https://hooks.slack.com/fake")

    notifier.notify(_stats())

    assert len(called) == 1
    url, kwargs = called[0]
    assert url == "https://hooks.slack.com/fake"
    assert kwargs["json"]["text"].startswith("[ALERT]")


def test_slack_notifier_raises_on_http_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_post(url: str, **kwargs: Any) -> Any:
        def raise_error() -> None:
            raise requests.exceptions.HTTPError("bad response")

        return SimpleNamespace(status_code=500, raise_for_status=raise_error)

    monkeypatch.setattr(requests, "post", fake_post)
    notifier = SlackNotifier("https://hooks.slack.com/fake")

    with pytest.raises(NotificationError):
        notifier.notify(_stats())

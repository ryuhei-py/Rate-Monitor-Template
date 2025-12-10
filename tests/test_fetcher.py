"""Tests for data fetching."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, List

import pytest
import requests

from rate_monitor.fetcher import FetchError, Fetcher


def _response(status: int, text: str = "") -> Any:
    return SimpleNamespace(status_code=status, text=text)


def test_successful_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    def fake_get(url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return _response(200, "ok")

    monkeypatch.setattr(requests, "get", fake_get)
    fetcher = Fetcher(timeout=1, max_retries=3)

    assert fetcher.get("https://example.com") == "ok"
    assert len(calls) == 1


def test_retry_on_5xx_then_success(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []
    responses = iter([_response(502), _response(200, "recovered")])

    def fake_get(url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return next(responses)

    monkeypatch.setattr(requests, "get", fake_get)
    fetcher = Fetcher(timeout=1, max_retries=3)

    assert fetcher.get("https://example.com/retry") == "recovered"
    assert len(calls) == 2


def test_no_retry_on_4xx(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    def fake_get(url: str, **kwargs: Any) -> Any:
        calls.append(url)
        return _response(404)

    monkeypatch.setattr(requests, "get", fake_get)
    fetcher = Fetcher(timeout=1, max_retries=5)

    with pytest.raises(FetchError):
        fetcher.get("https://example.com/notfound")
    assert len(calls) == 1


def test_fetch_error_after_all_retries(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: List[str] = []

    def fake_get(url: str, **kwargs: Any) -> Any:
        calls.append(url)
        raise requests.exceptions.ConnectionError("boom")

    monkeypatch.setattr(requests, "get", fake_get)
    fetcher = Fetcher(timeout=0.1, max_retries=2)

    with pytest.raises(FetchError):
        fetcher.get("https://example.com/fail")
    assert len(calls) == 2

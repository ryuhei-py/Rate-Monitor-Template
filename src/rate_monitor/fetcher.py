"""HTTP fetcher with simple retry support."""

from __future__ import annotations

from typing import Dict, Optional

import requests
from requests import Response


class FetchError(RuntimeError):
    """Raised when fetching a URL fails after retries."""

    def __init__(self, url: str, status: Optional[int], message: str | None = None) -> None:
        self.url = url
        self.status = status
        self.message = message or "Failed to fetch URL"
        super().__init__(f"{self.message}: {url} (status={status})")


class Fetcher:
    """Lightweight HTTP client with retry on transient failures."""

    DEFAULT_HEADERS: Dict[str, str] = {
        "User-Agent": "rate-monitor/0.1 (+https://example.com)",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self, timeout: float = 10.0, max_retries: int = 3, headers: dict | None = None) -> None:
        self.timeout = timeout
        self.max_retries = max(1, max_retries)
        self.headers = {**self.DEFAULT_HEADERS, **(headers or {})}

    def _should_retry(self, response: Response | None, exc: Exception | None) -> bool:
        if exc is not None:
            return True
        if response is None:
            return False
        return 500 <= response.status_code < 600

    def get(self, url: str) -> str:
        """Fetch a URL and return the body text, retrying on transient failures."""
        last_status: Optional[int] = None
        for attempt in range(self.max_retries):
            response: Response | None = None
            error: Exception | None = None
            try:
                response = requests.get(url, headers=self.headers, timeout=self.timeout)
                last_status = response.status_code
                if 200 <= response.status_code < 300:
                    return response.text
                if not self._should_retry(response, None):
                    break
            except requests.exceptions.RequestException as exc:
                error = exc
            if attempt == self.max_retries - 1 or not self._should_retry(response, error):
                break
        raise FetchError(url, last_status)

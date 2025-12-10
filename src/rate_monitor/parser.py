"""HTML parsing utilities for extracting a single rate value."""

from __future__ import annotations

import re
from bs4 import BeautifulSoup

class ParseError(Exception):
    """Raised when a rate value cannot be parsed from the HTML."""
    pass

class RatePageParser:
    def __init__(self, selector: str) -> None:
        self.selector = selector

    def parse(self, html: str) -> float:
        soup = BeautifulSoup(html, "html.parser")
        elem = soup.select_one(self.selector)
        if elem is None:
            raise ParseError(f"No element found for selector {self.selector!r}")

        raw_text = elem.get_text(strip=True)

        # Strip common currency symbols and whitespace
        text = raw_text.strip()
        text = text.replace("¥", "").replace("$", "").replace("€", "")
        text = text.replace(" ", "")

                # Handle thousands separators vs decimal separators
        if "," in text and "." not in text:
            # Only comma present: decide if it's thousands or decimal separator
            left, right = text.rsplit(",", 1)
            if len(right) == 3 and left.isdigit() and right.isdigit():
                # Case like "1,234" → thousands separator: remove comma
                normalized = left + right
            else:
                # Treat comma as decimal separator, e.g. "1,23"
                normalized = text.replace(",", ".")
        elif "," in text and "." in text:
            # Both comma and dot present: assume comma is thousands separator,
            # dot is decimal separator. Example: "1,234.56" → "1234.56"
            normalized = text.replace(",", "")
        else:
            # No comma, maybe just a plain decimal like "1234.56"
            normalized = text

        try:
            value = float(normalized)
        except ValueError as exc:
            raise ParseError(f"Could not parse rate value from {raw_text!r}") from exc

        return value

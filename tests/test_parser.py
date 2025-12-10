"""Tests for data parsing."""

import pytest

from rate_monitor.parser import ParseError, RatePageParser


def test_parse_simple_number() -> None:
    html = "<div class='price'>123.45</div>"
    parser = RatePageParser(".price")

    assert parser.parse(html) == 123.45


def test_parse_number_with_comma() -> None:
    html = "<span id='value'>1,234</span>"
    parser = RatePageParser("#value")

    assert parser.parse(html) == 1234.0


def test_parse_currency_symbol() -> None:
    html = "<p class='rate'>¥1,234.56</p>"
    parser = RatePageParser(".rate")

    assert parser.parse(html) == 1234.56


def test_parse_error_on_invalid_html() -> None:
    html = "<html><body><div>No number here</div></body></html>"
    parser = RatePageParser(".missing")

    with pytest.raises(ParseError):
        parser.parse(html)

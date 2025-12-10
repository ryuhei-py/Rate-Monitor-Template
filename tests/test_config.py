"""Tests for configuration utilities."""

from pathlib import Path

import pytest

from rate_monitor.config import (
    ConfigError,
    AlertsSettings,
    DBSettings,
    MonitoringSettings,
    Settings,
    SlackSettings,
    TargetConfig,
    load_settings,
    load_targets,
)


def test_load_targets_parses_configs(tmp_path: Path) -> None:
    content = """\
targets:
  - id: btc
    name: Bitcoin
    url: https://example.com/btc
    selector: div.price
  - id: eth
    name: Ethereum
    url: https://example.com/eth
    selector: span.value
"""
    file_path = tmp_path / "targets.yml"
    file_path.write_text(content, encoding="utf-8")

    targets = load_targets(str(file_path))

    assert targets == [
        TargetConfig(id="btc", name="Bitcoin", url="https://example.com/btc", selector="div.price"),
        TargetConfig(id="eth", name="Ethereum", url="https://example.com/eth", selector="span.value"),
    ]


def test_load_targets_missing_required_fields(tmp_path: Path) -> None:
    content = """\
- id: missing_name
  url: https://example.com
  selector: div.price
"""
    file_path = tmp_path / "targets.yml"
    file_path.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigError):
        load_targets(str(file_path))


def test_load_settings_with_defaults_and_overrides(tmp_path: Path) -> None:
    content = """\
db:
  path: ./data/custom.db
monitoring:
  interval_seconds: 120
alerts:
  enabled: true
  threshold: 10.5
slack:
  webhook_url: https://hooks.example/abc
  channel: alerts
"""
    file_path = tmp_path / "settings.yml"
    file_path.write_text(content, encoding="utf-8")

    settings = load_settings(str(file_path))

    assert settings.db == DBSettings(path="./data/custom.db")
    assert settings.monitoring == MonitoringSettings(interval_seconds=120)
    assert settings.alerts == AlertsSettings(enabled=True, threshold=10.5)
    assert settings.slack == SlackSettings(webhook_url="https://hooks.example/abc", channel="alerts")


def test_load_settings_invalid_structure_raises(tmp_path: Path) -> None:
    file_path = tmp_path / "settings.yml"
    file_path.write_text("- not a mapping", encoding="utf-8")

    with pytest.raises(ConfigError):
        load_settings(str(file_path))


def test_load_settings_uses_defaults_when_missing(tmp_path: Path) -> None:
    file_path = tmp_path / "settings.yml"
    file_path.write_text("", encoding="utf-8")

    settings = load_settings(str(file_path))

    assert settings.db == DBSettings()
    assert settings.monitoring == MonitoringSettings()
    assert settings.alerts == AlertsSettings()
    assert settings.slack == SlackSettings()

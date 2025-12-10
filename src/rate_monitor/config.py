"""Configuration handling for the rate monitor service."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List

import yaml


class ConfigError(ValueError):
    """Raised when configuration files are invalid or incomplete."""


@dataclass
class TargetConfig:
    """Individual target definition used by the rate monitor."""

    id: str
    name: str
    url: str
    selector: str


@dataclass
class DBSettings:
    """Database configuration section."""

    path: str = "./data/rates.db"


@dataclass
class MonitoringSettings:
    """Monitoring configuration section."""

    interval_seconds: int = 300


@dataclass
class AlertsSettings:
    """Alerting configuration section."""

    enabled: bool = False
    threshold: float | None = None


@dataclass
class SlackSettings:
    """Slack notification configuration section."""

    webhook_url: str | None = None
    channel: str | None = None


@dataclass
class Settings:
    """Container for all runtime settings."""

    db: DBSettings = field(default_factory=DBSettings)
    monitoring: MonitoringSettings = field(default_factory=MonitoringSettings)
    alerts: AlertsSettings = field(default_factory=AlertsSettings)
    slack: SlackSettings = field(default_factory=SlackSettings)


def _require_fields(data: Dict[str, Any], required: List[str], context: str) -> None:
    missing = [field for field in required if field not in data or data[field] in (None, "")]
    if missing:
        raise ConfigError(f"Missing required fields {missing} in {context}")


def load_targets(path: str) -> List[TargetConfig]:
    """Load target configurations from a YAML file."""
    raw = yaml.safe_load(_read_file(path))
    if raw is None:
        return []

    if isinstance(raw, dict):
        if "targets" not in raw:
            raise ConfigError('Expected a "targets" list in the YAML content.')
        raw_targets = raw["targets"]
    elif isinstance(raw, list):
        raw_targets = raw
    else:
        raise ConfigError("Targets YAML must be a list or contain a top-level 'targets' key.")

    targets: List[TargetConfig] = []
    for idx, item in enumerate(raw_targets):
        if not isinstance(item, dict):
            raise ConfigError(f"Target entry at index {idx} must be a mapping.")
        _require_fields(item, ["id", "name", "url", "selector"], f"target {idx}")
        targets.append(
            TargetConfig(
                id=str(item["id"]),
                name=str(item["name"]),
                url=str(item["url"]),
                selector=str(item["selector"]),
            )
        )
    return targets


def load_settings(path: str) -> Settings:
    """Load application settings from a YAML file."""
    raw = yaml.safe_load(_read_file(path)) or {}
    if not isinstance(raw, dict):
        raise ConfigError("Settings YAML must be a mapping/object.")

    db_section = raw.get("db", {})
    monitoring_section = raw.get("monitoring", {})
    alerts_section = raw.get("alerts", {})
    slack_section = raw.get("slack", {})

    if db_section is not None and not isinstance(db_section, dict):
        raise ConfigError("db section must be a mapping.")
    if monitoring_section is not None and not isinstance(monitoring_section, dict):
        raise ConfigError("monitoring section must be a mapping.")
    if alerts_section is not None and not isinstance(alerts_section, dict):
        raise ConfigError("alerts section must be a mapping.")
    if slack_section is not None and not isinstance(slack_section, dict):
        raise ConfigError("slack section must be a mapping.")

    db_settings = DBSettings(path=db_section.get("path", DBSettings().path))
    monitoring_settings = MonitoringSettings(
        interval_seconds=int(monitoring_section.get("interval_seconds", MonitoringSettings().interval_seconds))
    )
    alerts_settings = AlertsSettings(
        enabled=bool(alerts_section.get("enabled", AlertsSettings().enabled)),
        threshold=alerts_section.get("threshold", AlertsSettings().threshold),
    )
    slack_settings = SlackSettings(
        webhook_url=slack_section.get("webhook_url"),
        channel=slack_section.get("channel"),
    )

    return Settings(
        db=db_settings,
        monitoring=monitoring_settings,
        alerts=alerts_settings,
        slack=slack_settings,
    )


def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    except FileNotFoundError as exc:
        raise ConfigError(f"Configuration file not found: {path}") from exc

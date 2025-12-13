"""Tests for database layer."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import sqlite3

from rate_monitor.db import RateDatabase


def test_init_schema_creates_table(tmp_path: Path) -> None:
    db_path = tmp_path / "rates.db"
    db = RateDatabase(str(db_path))

    db.init_schema()

    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='rates'"
        )
        assert cursor.fetchone() is not None


def test_insert_and_get_history_round_trip(tmp_path: Path) -> None:
    db_path = tmp_path / "rates.db"
    db = RateDatabase(str(db_path))
    db.init_schema()

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    recent = now - timedelta(hours=1)
    old = now - timedelta(days=5)

    db.insert_rate("target-a", recent, 10.0)
    db.insert_rate("target-a", now, 12.5)
    db.insert_rate("target-a", old, 5.0)  # should be filtered out
    db.insert_rate("target-b", now, 99.9)  # different target

    history = db.get_history("target-a", days=2)

    assert len(history) == 2
    assert history[0][0] == recent
    assert history[0][1] == 10.0
    assert history[1][0] == now
    assert history[1][1] == 12.5

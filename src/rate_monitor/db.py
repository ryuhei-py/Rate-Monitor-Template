"""Database interactions for persisting rates."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta,timezone
from pathlib import Path
from typing import List, Tuple


class RateDatabase:
    """SQLite-backed time-series storage for rate data."""

    def __init__(self, db_path: str) -> None:
        """Store DB path and ensure its parent directory exists.

        For in-memory databases (':memory:'), no directory is created.
        """
        # Convert to a Path object
        self.db_path = Path(db_path)

        # Skip directory creation for in-memory DB
        if str(self.db_path) != ":memory__":
            # Automatically create parent directory if needed
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

    def init_schema(self) -> None:
        """Create required tables and indexes if they do not exist."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rates (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id TEXT NOT NULL,
                    ts TEXT NOT NULL,
                    value REAL NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_rates_target_ts ON rates (target_id, ts)")
            conn.commit()

    def insert_rate(self, target_id: str, timestamp: datetime, value: float) -> None:
        """Insert a single rate record."""
        with sqlite3.connect(str(self.db_path)) as conn:
            conn.execute(
                "INSERT INTO rates (target_id, ts, value) VALUES (?, ?, ?)",
                (target_id, timestamp.isoformat(), float(value)),
            )
            conn.commit()

    def get_history(self, target_id: str, days: int) -> List[Tuple[datetime, float]]:
        """Fetch rate history for a target within the requested window."""
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)
        with sqlite3.connect(str(self.db_path)) as conn:
            cursor = conn.execute(
                "SELECT ts, value FROM rates WHERE target_id = ? AND ts >= ? ORDER BY ts ASC",
                (target_id, cutoff.isoformat()),
            )
            rows = cursor.fetchall()
        history: List[Tuple[datetime, float]] = []
        for ts_str, value in rows:
            history.append((datetime.fromisoformat(ts_str), float(value)))
        return history

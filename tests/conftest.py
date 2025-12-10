"""
Test configuration for the rate-monitor-template project.

This file ensures that the `src/` layout is importable during tests.
"""

import sys
from pathlib import Path

# Project root = tests/ の1つ上のディレクトリ
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

# `src` を import パスの先頭に追加
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

"""Test configuration and fixtures placeholder."""
# TODO: Add shared pytest fixtures.

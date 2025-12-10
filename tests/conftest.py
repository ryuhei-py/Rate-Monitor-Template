"""
Pytest configuration for the rate-monitor-template project.

This file makes sure the src/ layout is importable as `rate_monitor`
when running tests.
"""

import sys
from pathlib import Path

# Project root directory (one level above tests/)
ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"

# Add src/ to sys.path so `import rate_monitor` works
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Testing

This document describes how to validate correctness and prevent regressions for the Rate Monitor Template. The test suite is intentionally deterministic and offline-friendly: it does **not** depend on live websites or real third-party services.

---

## Goals and Scope

### Goals
- Validate the core pipeline behavior: **fetch → parse → store → analyze → notify → export**.
- Keep tests **repeatable** and **fast**, suitable for continuous integration.
- Cover both normal flows and key failure modes (network errors, parse failures, insufficient history, notification errors).
- Provide a clear path for extending tests when adding new features (parsing formats, notifiers, configuration behavior).

### Non-goals
- Live end-to-end scraping against real websites (non-deterministic and ToS-dependent).
- Load/stress tests.
- Full scheduler execution tests (cron/Task Scheduler). Scheduling is treated as an operational concern.

---

## Test Coverage Map

The repository uses a `src/` layout and module-oriented tests. The table below maps each component to its primary coverage.

| Component                                                 | Responsibility                                                     | Test file(s)                   |
|-----------------------------------------------------------|--------------------------------------------------------------------|--------------------------------|
| `Fetcher` (`src/rate_monitor/fetcher.py`)                 | HTTP GET behavior, retries, and error classification               | `tests/test_fetcher.py`        |
| `RatePageParser` (`src/rate_monitor/parser.py`)           | CSS selector extraction and numeric normalization                  | `tests/test_parser.py`         |
| `RateDatabase` (`src/rate_monitor/db.py`)                 | SQLite schema creation, inserts, and time-windowed history queries | `tests/test_db.py`             |
| Analyzer (`src/rate_monitor/analyzer.py`)                 | Moving averages, percent deltas, and alert decision logic          | `tests/test_analyzer.py`       |
| Notifiers (`src/rate_monitor/notifier.py`)                | Stdout formatting and Slack webhook request behavior (mocked)      | `tests/test_notifier.py`       |
| Exporters (`src/rate_monitor/exporter.py`)                | CSV/JSON output structure and file creation                        | `tests/test_exporter.py`       |
| CLI orchestration (`src/rate_monitor/cli.py`)             | Dry-run flow, export invocation, notifier invocation               | `tests/test_cli.py`            |
| Scheduler examples (`src/rate_monitor/scheduler_stub.py`) | Presence/sanity of scheduler command examples                      | `tests/test_scheduler_stub.py` |
| Test import wiring                                        | Ensures `src/` is importable during tests                          | `tests/conftest.py`            |

---

## Test Strategy

### Deterministic and offline by design
- Tests do not call real websites.
- HTTP behavior is simulated by patching/mocking `requests.get` and `requests.post`.
- Files (SQLite DB, CSV, JSON) are written to temporary directories via `tmp_path`.

### Boundary-focused unit tests
Tests are organized around clear module boundaries:
- `Fetcher`: retry policy and failure behavior
- `Parser`: selector behavior and numeric normalization rules
- `DB`: schema and time-window filtering correctness
- `Analyzer`: calculation correctness and edge cases
- `Notifiers/Exporters`: side effects validated via mocks and filesystem assertions
- `CLI`: orchestration validated in dry-run mode via monkeypatching dependencies

---

## How to Run Tests Locally

### Prerequisites
- Python 3.11+ recommended (CI uses Python 3.12).
- A virtual environment is strongly recommended.

### Install dependencies
```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
````

### Run the full suite

```bash
pytest
```

### Useful variants

```bash
# Quiet output
pytest -q

# Run a single test module
pytest tests/test_parser.py

# Run tests matching a substring
pytest -k parser
```

### Run with CI-equivalent strictness (recommended)

CI treats DeprecationWarnings as errors:

```bash
PYTHONWARNINGS=error::DeprecationWarning pytest
```

---

## Notes on the `src/` Layout and Imports

This repository uses a `src/` layout. Tests work without installing the package because:

* `tests/conftest.py` adds `src/` to `sys.path`, enabling `import rate_monitor` during test execution.

This behavior is **test-only**. For runtime usage outside `pytest`, prefer either:

* setting `PYTHONPATH=src` when running the CLI, or
* configuring packaging so `pip install -e .` installs the `rate_monitor` package from `src/`.

---

## What the Tests Prove

### Fetching (HTTP)

Validated behavior includes:

* retries on transient failures (network exceptions) and server errors (HTTP 5xx)
* non-retry behavior on non-transient errors (e.g., HTTP 4xx)
* failure surfacing via the module’s exception type

### Parsing (HTML → float)

Validated behavior includes:

* selector-based extraction using a CSS selector
* numeric normalization for common formats (thousands separators, decimal separators, currency symbols)
* failures when no element matches the selector or conversion to float fails

### Storage (SQLite)

Validated behavior includes:

* schema creation and idempotent initialization
* inserting time-series observations
* retrieving history filtered by a *day-based* cutoff window

### Analysis and alerting logic

Validated behavior includes:

* moving averages computed over the last N observations
* percent delta calculations and safe handling when averages are unavailable or base is zero
* alert decision logic based on a threshold percentage
* behavior with insufficient history (no alert)

### Notifiers

Validated behavior includes:

* stdout notifier does not emit output when `should_alert` is false
* Slack notifier sends a webhook request only when `should_alert` is true
* Slack request failures are reported as module-level errors

### Exporters

Validated behavior includes:

* CSV output includes expected headers and rows
* JSON output includes expected fields derived from the stats dataclass
* output directories are created automatically

### CLI orchestration (dry-run)

Validated behavior includes:

* no DB insert calls during `--dry-run`
* exports are invoked
* notifier is invoked for each processed target

---

## CI Validation

The GitHub Actions workflow (`.github/workflows/ci.yml`) runs:

* dependency installation via `requirements.txt`
* `pytest` with `PYTHONWARNINGS=error::DeprecationWarning`

### What CI guarantees

* The unit-level behavior of the pipeline is continuously regression-tested.
* Changes to parsing, retry logic, DB behavior, alert logic, exporters, and notifier behavior are caught quickly.

### What CI does not guarantee

* Live scraping reliability against any specific website.
* Scheduler correctness (cron/Task Scheduler execution and environment behavior).
* End-to-end correctness for a specific deployment environment (proxy, network policy, SSL interception, etc.).

---

## Test Data, Fixtures, and Temporary Artifacts

### Inline fixtures

Many tests use inline YAML strings and HTML fragments to keep tests:

* readable,
* self-contained,
* portable.

### Temporary filesystem artifacts

Tests use `tmp_path` for:

* SQLite DB files (avoids persistent state)
* exported CSV/JSON files
* temporary settings files to validate config loading behavior

---

## Extending the Test Suite

### When to add tests

Add or update tests when you:

* change numeric parsing rules (new formats, new currencies, embedded text)
* modify fetch retry rules (e.g., add 429/backoff support)
* change how settings affect runtime behavior (e.g., configurable windows or alert enable flags)
* add a new notifier backend (email, Teams, Discord, etc.)
* expand exported data fields or output formats

### Recommended patterns

* Keep tests deterministic and avoid live I/O.
* Patch at the boundary:

  * HTTP requests (`requests.get`, `requests.post`)
  * time generation (only if behavior depends on the current time)
* Prefer explicit, minimal assertions that match the intended contract.

---

## Troubleshooting

### `ModuleNotFoundError: rate_monitor`

* Run `pytest` from the repository root.
* Confirm `tests/conftest.py` exists and `src/` is present.

### SQLite issues on Windows (file locks)

* If a test run is interrupted, SQLite files may remain locked briefly.
* Ensure the previous Python process has fully exited and rerun.

### Slack notifier test failures

* Slack tests do not call Slack; they patch `requests.post`.
* Failures generally indicate a changed payload format or alert gating behavior.

---

## Known Limitations (Intentional)

* No live website integration tests.
* No scheduler execution tests.
* No packaging installation test (e.g., a clean environment validation of `pip install -e .` + CLI execution).

These are deliberate trade-offs to keep tests fast, deterministic, and safe. They can be added as optional integration checks if the template is evolved into a deployment-ready service package.
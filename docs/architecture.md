# Architecture

This document describes the architecture of **Rate Monitor Template**: a config-driven, scheduler-friendly pipeline that monitors numeric rates/prices from web pages, persists time-series history in SQLite, computes baseline statistics, triggers alerts, and exports run artifacts.

---

## Table of Contents

- [Purpose and Scope](#purpose-and-scope)
- [System Overview](#system-overview)
- [Architecture at a Glance](#architecture-at-a-glance)
- [Runtime Flow](#runtime-flow)
- [Configuration Model](#configuration-model)
- [Core Modules](#core-modules)
- [Data Model](#data-model)
- [Exports and Artifacts](#exports-and-artifacts)
- [Error Handling and Reliability](#error-handling-and-reliability)
- [Operational Considerations](#operational-considerations)
- [Security and Compliance by Design](#security-and-compliance-by-design)
- [Testing Strategy](#testing-strategy)
- [Extensibility](#extensibility)
- [Known Gaps and Alignment Notes](#known-gaps-and-alignment-notes)
- [Appendix: Directory Structure](#appendix-directory-structure)
- [Appendix: Glossary](#appendix-glossary)

---

## Purpose and Scope

### Purpose
Rate Monitor Template is designed to:
- Monitor numeric values (“rates”) from web pages in a repeatable and configurable way.
- Persist time-series observations in a lightweight SQLite database.
- Compute simple baseline statistics (moving averages) and detect meaningful changes.
- Emit alerts (stdout by default; Slack webhook notifier is implemented).
- Export run outputs (CSV snapshot + JSON stats) for downstream usage.

### In scope
- Single-run batch execution via CLI, intended to be scheduled externally (cron / Windows Task Scheduler).
- HTML fetch → parse numeric value → store → analyze → notify → export.
- SQLite persistence and history retrieval.

### Out of scope (by design)
- Long-running daemon loop (interval execution is handled by external scheduling).
- Site-specific bypassing, CAPTCHA handling, robots.txt enforcement, or authentication flows.
- High-scale crawling, distributed execution, or built-in concurrency.

---

## System Overview

### What it monitors
Any target where the latest numeric value is present in HTML and can be extracted via a CSS selector:
- FX/crypto spot rates
- Product prices (where permitted)
- Public KPI tiles and dashboards (where permitted)

### What it produces
- **SQLite history**: appended rows `(target_id, timestamp, value)`
- **CSV snapshot** for the current run: `rates.csv`
- **JSON stats** for the current run: `latest_stats.json`
- **Alerts**:
  - Stdout alerts are supported by default.
  - Slack webhook notifier exists but requires configuration-model alignment to be selectable from YAML (documented in [Known Gaps and Alignment Notes](#known-gaps-and-alignment-notes)).

---

## Architecture at a Glance

### High-level component diagram
```mermaid
flowchart LR
  CLI["CLI (rate_monitor.cli)"] --> CFG["Config Loader (config.py)"]
  CLI --> F["Fetcher (fetcher.py)"]
  CLI --> P["Parser (parser.py)"]
  CLI --> DB["SQLite DB (db.py)"]
  CLI --> A["Analyzer (analyzer.py)"]
  CLI --> N["Notifier (notifier.py)"]
  CLI --> E["Exporter (exporter.py)"]

  F -->|HTML| P
  P -->|float value| CLI
  CLI -->|insert/query| DB
  DB -->|history| A
  A -->|RateStats| N
  CLI -->|rows + stats| E
````

### Design principles (why it is structured this way)

* **Config-driven**: targets and key parameters are externalized for fast adaptation.
* **Boundary isolation**: network, parsing, persistence, analysis, notifications, exports are separate modules.
* **Scheduler-friendly**: one run equals one deterministic batch, enabling clean cron/Task Scheduler operation.
* **Testability**: modules are small and mock-friendly; tests avoid live network dependencies.

---

## Runtime Flow

### Entry point and CLI arguments

Entrypoint:

* `python -m rate_monitor.cli`

Arguments:

* `--targets` (default: `config/targets.example.yml`)
* `--settings` (default: `config/settings.example.yml`)
* `--output-dir` (default: `sample_output`)
* `--dry-run` (flag; skips DB inserts)

### Single-run lifecycle (exact flow)

1. Load settings from YAML.
2. Load targets from YAML.
3. Initialize SQLite schema (table + index).
4. For each target:

   * Fetch HTML from the target URL.
   * Parse a numeric value using the target’s CSS selector.
   * Insert into SQLite (skipped in dry-run).
   * Retrieve recent history from SQLite (time-windowed by days).
   * Analyze history to produce `RateStats` (moving averages over last N observations).
   * Notify when alert conditions are met.
   * Append export rows for the current run.
5. Write exports: CSV snapshot (`rates.csv`) and JSON stats (`latest_stats.json`).

### Dry-run behavior

Dry-run is intended to validate configuration safely:

* No SQLite writes occur.
* Fetching and parsing still happen (real HTTP requests are performed).
* The current observation is appended in-memory to the fetched history before analysis.
* Exports still run.

---

## Configuration Model

All configuration is loaded from YAML via `rate_monitor.config`.

### Targets configuration

Supported YAML shapes:

* A top-level mapping with `targets: [...]`, or
* A top-level list `[...]`

Each target must define:

* `id`: stable identifier (used as the DB key)
* `name`: human-readable label
* `url`: page URL to fetch
* `selector`: CSS selector that identifies the value element in the HTML

Operational note:

* The default `config/targets.example.yml` in this template is fully commented. If used without modification, YAML loads as `null`, resulting in **zero targets processed**. For real runs, create an active targets file with actual entries.

### Settings configuration

Supported sections and fields (as implemented):

#### `db`

* `path` (string, default: `./data/rates.db`)

#### `monitoring`

* `interval_seconds` (int, default: `300`)

  * Parsed and stored in settings, but **not used** to drive a runtime loop. Scheduling is intended to be external.

#### `alerts`

* `enabled` (bool, default: `false`)

  * Parsed but **not enforced** by the CLI runtime (see [Known Gaps](#known-gaps-and-alignment-notes)).
* `threshold` (float | null)

  * Used as the percent change threshold.
  * If unset (`null`), the CLI treats it as `0.0` when selecting the threshold.

#### `slack`

* `webhook_url` (string | null)
* `channel` (string | null)

  * Parsed but not used in Slack payload construction.

---

## Core Modules

### `rate_monitor.cli`

**Role**: Orchestrates a single end-to-end run.

Key responsibilities:

* Parse CLI arguments.
* Load settings/targets.
* Initialize database schema.
* Run the per-target pipeline.
* Export CSV/JSON.
* Handle top-level failure reporting.

Important runtime defaults:

* Analysis windows are currently hard-coded in the CLI:

  * `window_short = 3` (observations)
  * `window_long = 7` (observations)
* History query uses a time cutoff:

  * `days = window_long` (i.e., last 7 days)

Failure model:

* A broad top-level exception handler aborts the run on any unhandled exception and prints a single `Error: ...` line to stderr.

### `rate_monitor.config`

**Role**: Typed YAML configuration loader.

Responsibilities:

* Convert YAML into dataclasses (`TargetConfig`, `Settings`, etc.).
* Validate required fields and fail fast on invalid structure.

Guarantees:

* If a targets file parses as `null`, it returns an empty list (no targets), not an exception.

### `rate_monitor.fetcher`

**Role**: Network access boundary (HTTP GET).

Behavior:

* Uses `requests.get(..., timeout=10)`.
* Sets basic headers including a static User-Agent string.
* Retries on:

  * network exceptions (`requests.exceptions.RequestException`)
  * HTTP 5xx responses
* Does not retry on HTTP 4xx by default (including 429).

Errors:

* Raises `FetchError` after retry exhaustion.

### `rate_monitor.parser`

**Role**: HTML-to-float conversion boundary.

Behavior:

* Uses BeautifulSoup with `select_one(selector)` to find a single element.
* Extracts `.get_text(strip=True)`.
* Normalizes common numeric formats:

  * Strips currency symbols (`¥`, `$`, `€`)
  * Handles comma/dot thousands and decimal conventions
* Converts to `float`.

Errors:

* Raises `ParseError` if the selector does not match or conversion fails.

### `rate_monitor.db`

**Role**: SQLite persistence and history retrieval.

Responsibilities:

* Initialize schema.
* Insert new observations.
* Retrieve recent history for analysis.

Schema:

* Table `rates(id, target_id, ts, value)`
* Index on `(target_id, ts)`.

Timestamp semantics:

* The CLI uses `datetime.now(timezone.utc).replace(tzinfo=None)`:

  * timestamps are **naive UTC** (no offset stored)
* Stored as ISO strings (`ts.isoformat()`).

History retrieval:

* `get_history(target_id, days=N)` filters rows with `ts >= cutoff.isoformat()` where cutoff is computed as “now UTC minus N days”.

Implementation note:

* The in-memory DB special-case check uses `:memory__` rather than SQLite’s conventional `:memory:`. This is a minor edge-case issue (see [Known Gaps](#known-gaps-and-alignment-notes)).

### `rate_monitor.analyzer`

**Role**: Baselines, percent deltas, and alert decision.

Inputs:

* Time-ordered history `[(timestamp, value), ...]`
* Short/long observation windows
* Percent threshold
* Target id

Outputs:

* `RateStats` including:

  * `current`
  * `short_avg`, `long_avg`
  * `change_from_short_pct`, `change_from_long_pct`
  * `should_alert`, `reason`

Alert logic:

* Triggers when `abs(change_pct) > threshold_percent` (strictly greater-than).
* If `base == 0` or insufficient history for a window, percent change is `None`.

Analytical nuance:

* Moving averages are computed over the tail that includes the most recent observation (the “current” point). This tends to reduce the apparent delta compared to a baseline that excludes the current value.

### `rate_monitor.notifier`

**Role**: Alert delivery boundary.

Implementations:

* `StdoutNotifier`

  * Prints alerts only when `should_alert` is true.
* `SlackNotifier`

  * Posts to an incoming webhook with JSON payload `{"text": "..."}`
  * Uses `requests.post(..., timeout=5)`

Notes:

* `slack.channel` is not used in payload construction.
* Slack notifier selection from YAML is not fully aligned with the settings model (see [Known Gaps](#known-gaps-and-alignment-notes)).

Errors:

* Raises `NotificationError` on Slack POST failures.

### `rate_monitor.exporter`

**Role**: Export run artifacts.

CSV (`rates.csv`):

* Header: `timestamp,target_id,value`
* One row per target in the current run (snapshot), not full history.

JSON (`latest_stats.json`):

* List of `RateStats` values as dictionaries.

Filesystem behavior:

* Ensures parent directories exist before writing.

### `rate_monitor.scheduler_stub`

**Role**: Scheduling examples.

* Contains example command strings for cron / Task Scheduler usage.
* There is no runtime scheduler dependency; scheduling is external by design.

---

## Data Model

### Domain types

#### TargetConfig

* `id` (string): stable identifier for DB and exports
* `name` (string): human label
* `url` (string): fetch URL
* `selector` (string): CSS selector for extraction

#### RateStats

* `target_id` (string)
* `current` (float)
* `short_avg` (float | null)
* `long_avg` (float | null)
* `change_from_short_pct` (float | null)
* `change_from_long_pct` (float | null)
* `should_alert` (bool)
* `reason` (string)

### SQLite schema

```sql
CREATE TABLE IF NOT EXISTS rates (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  target_id TEXT NOT NULL,
  ts TEXT NOT NULL,
  value REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_rates_target_ts
ON rates (target_id, ts);
```

---

## Exports and Artifacts

### `rates.csv` (current-run snapshot)

Purpose:

* Provide the latest observed value per target for this run in a simple, tool-friendly format.

Characteristics:

* Snapshot only (not historical export).
* One line per target processed.

### `latest_stats.json` (current-run computed stats)

Purpose:

* Provide analysis results and alert decisions in a machine-readable form.

Characteristics:

* Contains baseline comparisons and `should_alert` decisions.
* Intended for dashboards, pipelines, or additional automation steps.

---

## Error Handling and Reliability

### Error categories

* Fetch failures (network exceptions, HTTP errors)
* Parse failures (selector missing, non-numeric value)
* DB failures (SQLite read/write, filesystem)
* Notification failures (Slack webhook)
* Export failures (permissions, path issues)

### Current reliability characteristics

* Retries exist only for transient fetch failures (network exceptions, 5xx).
* No explicit backoff strategy for rate limiting (429).
* One unhandled exception aborts the entire run.
* No per-target isolation is implemented.

Operational implications:

* Use conservative scheduling and consider backoff if targets can rate-limit.
* If monitoring many heterogeneous targets, consider isolating failures per target (extension).

---

## Operational Considerations

### Scheduling model

This project is intended to run under an external scheduler:

* cron (Linux/macOS)
* Windows Task Scheduler

`monitoring.interval_seconds` is currently not used to run an internal loop.

### Storage growth and retention

SQLite will grow as each run appends points:

* Define a retention policy (e.g., keep last 90 days).
* Back up the DB if it becomes a valuable dataset.
* Consider maintenance routines (vacuum/compaction) for long-running deployments.

### Observability

Current behavior:

* Alerts go to stdout.
* Errors print a single line to stderr.

Common production improvements (optional extensions):

* Structured logs (JSON)
* Per-target status reporting
* Run duration metrics and success/failure counters

See `docs/operations.md` for operational practices.

---

## Security and Compliance by Design

This template is intentionally conservative:

* No authentication bypass features.
* No scraping evasion mechanisms.
* External scheduling provides explicit control of request rate.
* The operator must ensure targets comply with site Terms of Service and applicable laws.

Secrets handling:

* Slack webhook URLs should be treated as secrets and managed via secure mechanisms.
* `.env.example` exists, but runtime does not automatically load `.env` without additional implementation (see [Known Gaps](#known-gaps-and-alignment-notes)).

See `docs/SECURITY_AND_LEGAL.md` for broader guidance.

---

## Testing Strategy

### What is tested

The test suite is unit-test focused and avoids live network dependency:

* Fetcher retry behavior (mocked)
* Parser normalization and failure cases
* SQLite schema creation and history filtering
* Analyzer calculations and alert logic
* Notifier behavior (Slack mocked)
* Exporter CSV/JSON output
* CLI orchestration in dry-run mode (via monkeypatching)
* Scheduler stub content

### What is intentionally not tested

* Live scraping against real sites (nondeterministic and ToS-sensitive).

CI:

* GitHub Actions runs pytest.
* `tests/conftest.py` adds `src/` to `sys.path` to allow imports during tests without installing the package.

See `docs/testing.md` for commands and coverage notes.

---

## Extensibility

The codebase is intentionally modular. Common extension paths:

* Add per-target request configuration (headers, timeouts, proxies).
* Add alternative parsers (regex-based numeric extraction, JSON endpoints).
* Make analysis windows configurable and clarify “days vs observations”.
* Improve baselines (exclude current observation from averages, robust statistics).
* Add notifier backends (Email, Teams, generic webhooks).
* Add retention and maintenance commands (delete old rows, compact DB).
* Add per-target isolation to prevent one failing target from aborting the run.

---

## Known Gaps and Alignment Notes

This section documents current mismatches and limitations so the repository remains credible and internally consistent.

### Slack enablement mismatch

* Example settings may include `slack.enabled`, but the current `SlackSettings` model does not define `enabled`.
* Notifier selection uses `getattr(settings.slack, "enabled", False)`, so it defaults to stdout in practice.
* `slack.channel` is parsed but not used in Slack payload construction.

### `alerts.enabled` is parsed but not enforced

* The CLI uses only `alerts.threshold` to decide whether to trigger alerts.

### `monitoring.interval_seconds` is parsed but not used at runtime

* Execution frequency is intended to be controlled by external scheduling.

### Analysis windows are hard-coded in the CLI

* `window_short = 3`, `window_long = 7` (observation-based moving averages).
* History retrieval uses a time window of `days = 7` (last 7 days), which is not the same concept as “last 7 observations” if scheduled frequently.

### `.env` and environment variables

* `.env.example` exists and `python-dotenv` is listed in dependencies.
* Runtime code does not currently load `.env` automatically.

### SQLite in-memory special-case typo

* The DB constructor special-cases `:memory__` (typo vs SQLite’s conventional `:memory:`).
* This mainly affects directory creation behavior when using in-memory DBs.

---

## Appendix: Directory Structure

```text
.github/workflows/ci.yml

config/
  settings.example.yml
  targets.example.yml

docs/
  architecture.md
  CONFIG_GUIDE.md
  operations.md
  SECURITY_AND_LEGAL.md
  testing.md

src/rate_monitor/
  analyzer.py
  cli.py
  config.py
  db.py
  exporter.py
  fetcher.py
  notifier.py
  parser.py
  scheduler_stub.py

tests/
  conftest.py
  test_analyzer.py
  test_cli.py
  test_config.py
  test_db.py
  test_exporter.py
  test_fetcher.py
  test_notifier.py
  test_parser.py
  test_scheduler_stub.py
  test_smoke.py

sample_output/
  latest_stats.json
  rates.csv
  rates.sample.csv

data/
  rates.db
```

---

## Appendix: Glossary

* **Target**: A monitored entity defined in YAML (`url` + `selector`).
* **Selector**: CSS selector used to locate the value element in HTML.
* **History window (days)**: Time cutoff used for querying recent rows from SQLite.
* **Analysis window (observations)**: Count of recent points used for moving averages.
* **Threshold**: Percent change limit that triggers an alert.
* **Dry-run**: Execution mode that avoids DB writes while still fetching, parsing, analyzing, and exporting.
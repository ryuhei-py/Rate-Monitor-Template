# Operations Guide

This document describes how to run, schedule, observe, and maintain the **Rate Monitor Template** safely and reliably. It is aligned with the current implementation under `src/rate_monitor/` and documents operational behavior as it actually exists today.

---

## Contents

- [Operational Model](#operational-model)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
  - [Targets (`config/targets.yml`)](#targets-configtargetsyml)
  - [Settings (`config/settings.yml`)](#settings-configsettingsyml)
  - [Secrets and Environment Variables](#secrets-and-environment-variables)
- [Running the Monitor](#running-the-monitor)
  - [Ad-hoc Run](#ad-hoc-run)
  - [Dry-run Mode](#dry-run-mode)
  - [Exit Codes](#exit-codes)
- [Outputs and Data](#outputs-and-data)
  - [SQLite Database](#sqlite-database)
  - [CSV Snapshot (`rates.csv`)](#csv-snapshot-ratescsv)
  - [JSON Stats (`latest_stats.json`)](#json-stats-latest_statsjson)
- [Alerting Semantics](#alerting-semantics)
- [Scheduling](#scheduling)
  - [Linux/macOS (cron)](#linuxmacos-cron)
  - [Windows (Task Scheduler)](#windows-task-scheduler)
- [Reliability and Failure Modes](#reliability-and-failure-modes)
- [Logging and Observability](#logging-and-observability)
- [Data Lifecycle and Maintenance](#data-lifecycle-and-maintenance)
- [Security and Responsible Use](#security-and-responsible-use)
- [Troubleshooting](#troubleshooting)
- [Known Limitations](#known-limitations)
- [Operational Checklists](#operational-checklists)

---

## Operational Model

### What this project is

This project is a **single-run batch job** intended to be executed periodically by an external scheduler.

Each run performs a fixed pipeline:

1. Load settings (`config/settings.yml`) and targets (`config/targets.yml`)
2. For each target:
   - Fetch HTML from the target URL
   - Parse a single numeric value using a CSS selector
   - Insert the observation into SQLite (unless `--dry-run`)
   - Load recent history from SQLite
   - Compute moving-average deltas and decide whether an alert should fire
   - Notify (stdout by default; Slack notifier exists with wiring notes)
3. Export a per-run snapshot (`rates.csv`) and per-run stats (`latest_stats.json`)

### What this project is not

- Not a long-running service (no internal sleep loop).
- Not a crawler (it only requests explicitly configured URLs).
- Not a browser automation solution (no JS rendering, no captcha handling).
- Not a compliance engine (you must ensure your monitoring respects each site’s Terms of Service and policies).

---

## Prerequisites

### Runtime

- Python 3.11+ (per `pyproject.toml`)
- Network egress to the configured target URLs
- File system permissions to read/write:
  - SQLite DB path (default `./data/rates.db`)
  - Output directory (default `./sample_output/`)

### Recommended local layout

- Use a virtual environment for dependency isolation.
- Keep `data/` (SQLite), `logs/`, and `output/` under the repo root or a controlled directory with backups.

---

## Installation

### 1) Create and activate a virtual environment

#### Linux/macOS
```bash
python -m venv .venv
source .venv/bin/activate
````

#### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 2) Install dependencies

```bash
pip install -r requirements.txt
```

> Note: `requirements.txt` includes runtime dependencies and development/testing tools.

---

## Configuration

This project requires two configuration files:

* `config/targets.yml` — defines what to monitor
* `config/settings.yml` — defines where to store data and how to alert

### Create working config files

```bash
cp config/targets.example.yml config/targets.yml
cp config/settings.example.yml config/settings.yml
```

Important:

* `config/targets.example.yml` is fully commented in the template. A default run using only the example file can result in **zero targets processed**. Ensure you create and populate `config/targets.yml`.

---

### Targets (`config/targets.yml`)

#### Supported structure

Targets can be provided as:

* A mapping with a top-level `targets:` list, or
* A top-level YAML list

Each target entry must include:

* `id` (string): stable key for DB, exports, and stats
* `name` (string): human-readable label
* `url` (string): the page to fetch
* `selector` (string): CSS selector used with BeautifulSoup `select_one`

#### Minimal example

```yaml
targets:
  - id: usd_jpy
    name: USD/JPY
    url: "https://example.com/rates"
    selector: ".rate"
```

#### Operational guidance

* Keep `id` stable; changing it creates a new series in SQLite.
* Use selectors that match a single element with a clean numeric text.
* Re-validate selectors periodically; DOM changes are the most common operational failure cause.

---

### Settings (`config/settings.yml`)

#### Supported fields (current implementation)

```yaml
db:
  path: "./data/rates.db"

monitoring:
  interval_seconds: 300  # informational; scheduling is external

alerts:
  enabled: false         # parsed but not enforced by CLI
  threshold: 5.0         # percent threshold used by CLI

slack:
  webhook_url: ""        # stored; Slack selection requires wiring changes (see Known Limitations)
  channel: ""            # stored; not used by notifier
```

#### Important behavior

* `db.path` must be writable; the parent directory must be creatable.
* `alerts.threshold` is the only alert-related setting used by the CLI today:

  * If missing or `null`, the CLI treats it as `0.0`.
  * A threshold of `0.0` can create noisy alerts once enough history exists.

---

### Secrets and Environment Variables

This repo includes `.env.example`, but the current runtime **does not load `.env` automatically** and does not read Slack/webhook settings from environment variables.

Operationally safe approaches:

* Store secrets as OS-level environment variables or scheduler-managed secrets.
* For CI usage, store secrets in GitHub Actions Secrets.
* Do not commit secrets into YAML config files.

If you extend the runtime to load `.env`, ensure `.env` remains excluded (it is in `.gitignore`).

---

## Running the Monitor

### Source layout note (`src/` layout)

The code lives under `src/rate_monitor/`. To run without packaging changes, ensure `src/` is importable.

#### Linux/macOS

```bash
PYTHONPATH=src python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir sample_output
```

#### Windows PowerShell

```powershell
$env:PYTHONPATH = "src"
python -m rate_monitor.cli `
  --targets config/targets.yml `
  --settings config/settings.yml `
  --output-dir sample_output
```

### Ad-hoc run

Typical one-off run:

```bash
PYTHONPATH=src python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir output/runs/latest
```

### Dry-run mode

Dry-run is intended for safe target onboarding and selector verification.

```bash
PYTHONPATH=src python -m rate_monitor.cli --dry-run \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir output/runs/dry_run
```

Dry-run behavior:

* Does **not** insert rows into SQLite.
* Still fetches and parses live targets.
* Still computes analysis (it appends the current observation in-memory).
* Still exports CSV/JSON outputs.

### Exit codes

* `0`: run completed successfully
* `1`: an exception occurred (printed as `Error: ...` to stderr)

---

## Outputs and Data

A run produces up to three primary artifacts.

### SQLite Database

* Default: `./data/rates.db` (configurable via `db.path`)
* Schema:

  * Table `rates(id, target_id, ts, value)`
  * Index on `(target_id, ts)`

Timestamp semantics:

* The CLI stores timestamps as **naive UTC** ISO strings (timezone removed before storing).

Operational implications:

* Avoid concurrent runs writing to the same SQLite file.
* Backups are straightforward file copies when the job is idle.

---

### CSV Snapshot (`rates.csv`)

* Path: `<output-dir>/rates.csv`
* Columns: `timestamp,target_id,value`
* Semantics: **one row per processed target for the current run**

This file is a per-run snapshot, not a historical export.

---

### JSON Stats (`latest_stats.json`)

* Path: `<output-dir>/latest_stats.json`
* Structure: a list of per-target stats objects including:

  * `current`
  * `short_avg`, `long_avg`
  * `change_from_short_pct`, `change_from_long_pct`
  * `should_alert`
  * `reason`

---

## Alerting Semantics

### Windowing model

The analyzer computes moving averages over the **last N observations**, not “last N days.”

Current CLI values:

* short window: **3 observations**
* long window: **7 observations**

### Threshold model

An alert triggers when either of these is true:

* `abs(change_from_short_pct) > threshold`
* `abs(change_from_long_pct) > threshold`

Notes:

* The comparison is strictly `>` (not `>=`).
* If the baseline average is `0`, percent change is undefined and treated as `null`.

### Warm-up period

Alerts require enough history to compute averages:

* Fewer than 3 observations → short average is `null` → no short alerts
* Fewer than 7 observations → long average is `null` → no long alerts

Expect a natural warm-up period when deploying new targets.

### Analytical nuance (dampening)

The moving average is computed over the tail that includes the current observation. This slightly dampens deltas compared to baselines that exclude the latest point.

---

## Scheduling

Scheduling is external. Choose a cadence that is respectful of target sites and appropriate for the signal you want.

General guidance:

* Prefer longer intervals over aggressive polling.
* Align cadence with expected update frequency (e.g., hourly, daily).
* Avoid overlapping runs (especially with SQLite).

### Linux/macOS (cron)

Example: run hourly, create a timestamped output folder, and write logs.

```cron
0 * * * * cd /path/to/Rate-Monitor-Template && \
  . .venv/bin/activate && \
  PYTHONPATH=src python -m rate_monitor.cli \
    --targets config/targets.yml \
    --settings config/settings.yml \
    --output-dir output/runs/$(date +\%Y\%m\%d_\%H\%M) \
  >> logs/monitor.log 2>> logs/monitor.err
```

Recommendations:

* Keep `logs/` and `output/runs/` under a controlled directory.
* Use log rotation to avoid unbounded file growth.

### Windows (Task Scheduler)

Suggested approach:

* Action: start `powershell.exe`
* “Start in”: repository root directory
* Example command (adapt paths as needed):

```powershell
$env:PYTHONPATH="src"; .\.venv\Scripts\python.exe -m rate_monitor.cli --targets config\targets.yml --settings config\settings.yml --output-dir output\runs\latest
```

Common pitfalls:

* Wrong working directory (relative paths break).
* Insufficient permissions to write `data/` or `output/`.
* Overlapping runs due to long network timeouts.

---

## Reliability and Failure Modes

### Network failures

Fetcher behavior:

* Retries on network exceptions and HTTP 5xx.
* Does not implement special handling for HTTP 429 or backoff strategies.

Mitigations:

* Choose conservative schedules.
* If 429/blocks occur frequently, extend the fetcher with exponential backoff and/or use an approved API where available.

### Parsing failures

Typical causes:

* Selector mismatch due to DOM changes
* Locale differences affecting numeric formatting
* Bot mitigation returning alternate HTML

Mitigations:

* Validate new targets with `--dry-run`.
* Re-check selectors periodically.
* Prefer stable page elements (IDs/classes less likely to change).

### Single-point failure behavior

The CLI wraps the entire run; an uncaught failure will end the process with exit code 1.

Operational strategy:

* Keep high-risk targets isolated (separate schedules or separate runs) if partial success is required.
* Capture stderr and monitor for failures.

---

## Logging and Observability

Current behavior:

* Minimal stdout/stderr output
* No structured logging or metrics emission

Operational recommendations:

* Redirect stdout/stderr to log files in scheduled runs.
* Track basic run signals externally:

  * number of targets processed
  * alert count
  * run duration
  * error count

If extending:

* Add structured logging (JSON) and a small summary line per run.

---

## Data Lifecycle and Maintenance

### SQLite backups

SQLite is a single file. Backups can be performed by copying the file when the job is not running:

```bash
cp data/rates.db backups/rates_YYYYMMDD.db
```

### Retention

The DB grows over time. Consider:

* Periodic archival (copy DB, then start a fresh DB)
* Pruning old rows (requires a small maintenance script if you add one)

### Export retention

Exports are per-run snapshots. Recommended strategy:

* Write each run to a timestamped directory for traceability, or
* Overwrite a “latest” directory and rotate older outputs periodically.

---

## Security and Responsible Use

* Respect target site Terms of Service and applicable policies.
* Avoid aggressive scheduling and high request volume.
* Do not attempt to bypass access controls or bot protection.
* Treat Slack webhooks and output artifacts as potentially sensitive.
* Keep secrets out of repositories; use a secret manager or scheduler/CI secrets.

---

## Troubleshooting

### No targets processed (empty CSV/JSON)

Likely causes:

* Running with `config/targets.example.yml` (commented out)
* `config/targets.yml` missing or empty

Fix:

* Create and populate `config/targets.yml` with valid targets.

### `ModuleNotFoundError: No module named 'rate_monitor'`

Cause:

* `src/` not on `PYTHONPATH`

Fix:

* Run with `PYTHONPATH=src` as shown above.

### `ParseError: selector not found`

Cause:

* CSS selector does not match HTML returned

Fix:

* Update selector, re-test with `--dry-run`.

### `FetchError` (403 / 429)

Cause:

* Target site blocks or rate-limits automated traffic

Fix:

* Reduce cadence, adjust headers if appropriate, or use an approved API.
* Consider implementing backoff for 429 if you extend the project.

### Slack alerts not delivered

Cause:

* Slack notifier is not selectable via YAML as written (see Known Limitations)

Fix:

* Use stdout alerts or wire Slack enablement in code as part of a customization.

---

## Known Limitations

These items are included to precisely reflect current behavior:

1. **Slack notifier is implemented but not selectable via YAML as written**

   * Example config includes `slack.enabled`
   * `SlackSettings` does not define `enabled`
   * CLI checks `settings.slack.enabled` via `getattr(..., False)`, which resolves to `False`

2. **`alerts.enabled` is parsed but not enforced by the CLI**

   * Only `alerts.threshold` influences alert decisions

3. **`monitoring.interval_seconds` is informational**

   * Scheduling is external; the CLI does not loop

4. **Window sizes are hard-coded in the CLI**

   * short=3 observations, long=7 observations

5. **Exports are run snapshots**

   * `rates.csv` contains only the current run’s target rows

6. **Timestamp format**

   * DB stores naive UTC ISO timestamps
   * Sample CSV may show timezone offsets that are not produced by the current runtime

7. **SQLite in-memory special-case string**

   * DB code checks `":memory__"` instead of SQLite’s conventional `":memory:"`

---

## Operational Checklists

### Pre-deploy

* [ ] Create `config/targets.yml` with at least one valid target
* [ ] Confirm `config/settings.yml` DB path is writable
* [ ] Set `alerts.threshold` intentionally (avoid accidental `0.0`)
* [ ] Run once with `--dry-run` successfully
* [ ] Run once without `--dry-run` and confirm DB writes
* [ ] Confirm exports appear in the output directory

### Weekly maintenance

* [ ] Verify scheduled jobs are running and producing outputs
* [ ] Review logs for fetch/parse failures
* [ ] Validate selectors still match (spot-check with `--dry-run`)
* [ ] Backup `data/rates.db` if history matters
* [ ] Rotate logs/outputs to prevent unbounded growth

### Incident triage (fast path)

* [ ] Rerun with `--dry-run` to isolate DB vs fetch/parse issues
* [ ] If parse failures: update selectors and validate
* [ ] If fetch blocks: reduce cadence and reassess target policy
* [ ] If DB issues: restore from backup and prevent overlapping runs
# CONFIG_GUIDE

This document describes how to configure **Rate-Monitor-Template** accurately and safely.
It is written to match the **current implementation** under `src/rate_monitor/` (source of truth).

---

## Table of Contents

- [Configuration Surfaces](#configuration-surfaces)
- [Quick Setup Workflow](#quick-setup-workflow)
- [Targets Configuration (`targets.yml`)](#targets-configuration-targetsyml)
  - [Schema](#schema)
  - [Examples](#examples)
  - [Selector Guidance](#selector-guidance)
- [Settings Configuration (`settings.yml`)](#settings-configuration-settingsyml)
  - [Schema](#schema-1)
  - [Examples](#examples-1)
- [Environment Variables](#environment-variables)
- [Runtime Semantics (What the Tool Actually Does)](#runtime-semantics-what-the-tool-actually-does)
- [Slack Notifications](#slack-notifications)
- [Output Files](#output-files)
- [Validation and Error Handling](#validation-and-error-handling)
- [Practical Recipes](#practical-recipes)
- [Troubleshooting](#troubleshooting)
- [Security and Compliance Notes](#security-and-compliance-notes)
- [Appendix: Full Reference Examples](#appendix-full-reference-examples)

---

## Configuration Surfaces

### Files

- `config/targets.example.yml`  
  Defines **what to monitor** (URL + CSS selector + stable ID).
- `config/settings.example.yml`  
  Defines **global behavior** (SQLite DB path, alert threshold, Slack webhook fields).
- `.env` (optional)  
  A place to store secrets (e.g., Slack webhook URL). **Note:** the current code does not auto-load `.env`.

### CLI flags (how configuration is selected)

The CLI reads configuration from files with these defaults:

- `--targets` (default: `config/targets.example.yml`)
- `--settings` (default: `config/settings.example.yml`)
- `--output-dir` (default: `sample_output`)
- `--dry-run` (skip DB writes; still fetches URLs)

Example:
```bash
python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir output
````

---

## Quick Setup Workflow

1. Copy the examples into project-local files:

   ```bash
   cp config/targets.example.yml config/targets.yml
   cp config/settings.example.yml config/settings.yml
   cp .env.example .env
   ```

2. Edit `config/targets.yml` to add real targets.

3. Start with a dry-run to validate fetching/parsing and outputs:

   ```bash
   python -m rate_monitor.cli \
     --targets config/targets.yml \
     --settings config/settings.yml \
     --output-dir output \
     --dry-run
   ```

4. Run without `--dry-run` to persist history into SQLite:

   ```bash
   python -m rate_monitor.cli \
     --targets config/targets.yml \
     --settings config/settings.yml \
     --output-dir output
   ```

Important:

* The shipped `config/targets.example.yml` is **fully commented out** in this repository. If you run the CLI without creating a real targets file, the tool may load **zero targets** and produce empty outputs.

---

## Targets Configuration (`targets.yml`)

### What it controls

Targets define **what** the tool monitors. Each target is:

* a URL to fetch (HTML),
* a CSS selector to extract one numeric value from the HTML,
* a stable ID used in the database and exports.

### Accepted YAML shapes

The loader supports either:

* Mapping form:

  ```yaml
  targets:
    - ...
  ```
* List form:

  ```yaml
  - ...
  ```

### Schema

Each target must include all required fields:

| Field      | Type | Required | Meaning                                                                                   |
| ---------- | ---- | -------- | ----------------------------------------------------------------------------------------- |
| `id`       | str  | Yes      | Stable identifier used in SQLite and export outputs. Keep this constant once data exists. |
| `name`     | str  | Yes      | Human-readable label.                                                                     |
| `url`      | str  | Yes      | URL fetched via HTTP GET.                                                                 |
| `selector` | str  | Yes      | CSS selector passed to BeautifulSoup `select_one`.                                        |

Field requirements are enforced by configuration validation (missing keys raise `ConfigError`).

### Examples

#### Minimal (mapping form)

```yaml
targets:
  - id: usd_jpy
    name: USD/JPY (Example)
    url: https://example.com/rates/usd-jpy
    selector: ".rate-value"
```

#### Minimal (list form)

```yaml
- id: eur_usd
  name: EUR/USD (Example)
  url: https://example.com/rates/eur-usd
  selector: ".rate-value"
```

### Selector Guidance

This template parses **server-rendered HTML** (no browser/JS runtime). Selectors should match a value that is present in the initial HTML response.

Recommendations:

* Prefer stable identifiers (IDs or well-known class names).
* Avoid deeply nested selectors that depend on layout.
* If the value is rendered client-side (React/Vue/etc.), the selector will not find it in the fetched HTML.

What happens when the selector does not match:

* The parser raises `ParseError` (the run will terminate, because the CLI aborts on unhandled exceptions).

---

## Settings Configuration (`settings.yml`)

### What it controls

Settings define global behavior:

* SQLite database location (`db.path`)
* Alert threshold (`alerts.threshold`)
* Slack webhook fields (`slack.webhook_url`, `slack.channel`)

Note: Some fields are parsed but not currently used by the CLI runtime; see [Runtime Semantics](#runtime-semantics-what-the-tool-actually-does).

### Schema

#### `db`

| Field  | Type | Required | Default           | Meaning                                 |
| ------ | ---- | -------- | ----------------- | --------------------------------------- |
| `path` | str  | No       | `./data/rates.db` | SQLite file path for persisted history. |

Example:

```yaml
db:
  path: ./data/rates.db
```

#### `monitoring`

| Field              | Type | Required | Default | Meaning                                                                             |
| ------------------ | ---- | -------- | ------- | ----------------------------------------------------------------------------------- |
| `interval_seconds` | int  | No       | `300`   | Parsed and stored but not used by the current CLI runtime (scheduling is external). |

Example:

```yaml
monitoring:
  interval_seconds: 300
```

#### `alerts`

| Field       | Type  | Required | Default | Meaning                                                   |
| ----------- | ----- | -------- | ------- | --------------------------------------------------------- |
| `enabled`   | bool  | No       | `false` | Parsed but not used by the current CLI runtime.           |
| `threshold` | float | No       | `null`  | Percent threshold; if `null`, the CLI treats it as `0.0`. |

Example:

```yaml
alerts:
  enabled: true
  threshold: 5.0
```

#### `slack`

| Field         | Type | Required | Default | Meaning                                                              |
| ------------- | ---- | -------- | ------- | -------------------------------------------------------------------- |
| `webhook_url` | str  | No       | `null`  | Incoming webhook URL (used by `SlackNotifier` if Slack is selected). |
| `channel`     | str  | No       | `null`  | Stored but not used by the current Slack notifier implementation.    |

Example:

```yaml
slack:
  webhook_url: https://hooks.slack.com/services/XXX/YYY/ZZZ
  channel: "#alerts"
```

### Examples

#### Minimal settings (recommended starting point)

```yaml
db:
  path: ./data/rates.db

alerts:
  threshold: 5.0
```

#### Full example (all supported keys)

```yaml
db:
  path: ./data/rates.db

monitoring:
  interval_seconds: 300

alerts:
  enabled: true
  threshold: 5.0

slack:
  webhook_url: ""
  channel: "#alerts"
```

---

## Environment Variables

### Provided `.env.example`

This repository includes `.env.example` containing:

* `SLACK_WEBHOOK_URL`
* `SLACK_CHANNEL`

### Current runtime behavior (important)

The current implementation does **not**:

* automatically load `.env`, or
* read these environment variables.

If you want env-var-based secrets, introduce explicit `.env` loading (e.g., `python-dotenv`) and/or `os.getenv(...)` usage as an extension. Until then, treat `.env` as a storage convention rather than an active configuration input.

---

## Runtime Semantics (What the Tool Actually Does)

This section describes runtime behavior as implemented in `src/rate_monitor/cli.py`, `db.py`, and `analyzer.py`.

### 1) Execution model (single-run batch)

The CLI performs a single monitoring run:

* load settings
* load targets
* for each target: fetch → parse → (optionally) insert into SQLite → analyze → notify
* export outputs for the run

Scheduling (interval, cron, Task Scheduler) is intentionally external.

### 2) Analysis windows (fixed in current CLI)

The current CLI uses fixed window sizes:

* `window_short = 3`
* `window_long = 7`

These values are not configurable via `settings.yml` in the current implementation.

### 3) History retrieval uses *days*, averages use *observations*

* The database history retrieval uses a days-based cutoff:

  * `get_history(target_id, days=window_long)` → `days=7`
* Moving averages are computed over the **last N observations**:

  * short average: last 3 values
  * long average: last 7 values

Practical implication:

* If you run hourly, “7 observations” roughly represents ~7 hours of data.
* If you run daily, “7 observations” roughly represents a week.

### 4) Moving averages include the current observation

The average is taken over the tail that includes the most recent value (“current”).
This dampens the delta vs average compared to a baseline that excludes the current value.

### 5) Alert threshold behavior

The CLI uses:

* `threshold = settings.alerts.threshold or 0.0`

Meaning:

* If `alerts.threshold` is omitted or `null`, it becomes `0.0`.
* With enough history, any non-zero change can become alert-eligible.

Alerts trigger when:

* `abs(change_from_short_pct) > threshold` OR
* `abs(change_from_long_pct) > threshold`

### 6) Dry-run behavior

`--dry-run`:

* does not write to SQLite,
* still fetches URLs and parses rates,
* still produces exports,
* still computes stats by appending the current observed value to the in-memory history list.

---

## Slack Notifications

### What is implemented

* `SlackNotifier` exists and sends a JSON payload to an incoming webhook.
* It sends messages only when `should_alert` is true.

### Current limitation: Slack is not selectable via YAML as written

The CLI checks `settings.slack.enabled` when selecting the notifier, but:

* the `SlackSettings` schema does not define `enabled`.

As a result, Slack is effectively disabled through standard settings parsing in the current implementation.

If Slack enablement is required, the clean follow-up change is to:

* add `enabled: bool` to `SlackSettings`,
* parse it in `load_settings`,
* align `_select_notifier` with the schema.

Until then, stdout notifications are the effective default behavior.

---

## Output Files

All output paths are relative to `--output-dir` (default: `sample_output`).

### CSV: `rates.csv`

* Path: `<output-dir>/rates.csv`
* Contents: current run snapshot with header:

  * `timestamp,target_id,value`

This file is a **run snapshot**, not a full history export.

### JSON: `latest_stats.json`

* Path: `<output-dir>/latest_stats.json`
* Contents: list of per-target computed statistics:

  * current value
  * short/long moving averages (if enough data)
  * percent deltas
  * `should_alert`
  * `reason`

---

## Validation and Error Handling

### Configuration validation

* `settings.yml` must load as a mapping (dict); otherwise `ConfigError` is raised.
* Each target must include all required keys; missing fields raise `ConfigError`.
* Empty/fully-commented targets YAML loads as `null` and results in zero targets loaded.

### Runtime errors (common causes)

* **Fetch errors**: network issues, timeouts, repeated HTTP 5xx
* **Parse errors**: selector not found, non-numeric content
* **Notification errors**: Slack request failures (when SlackNotifier is used)
* **DB errors**: invalid paths, filesystem permissions

CLI behavior:

* The CLI aborts on the first unhandled exception and prints `Error: ...`.

---

## Practical Recipes

### Recipe: Add a new target safely

1. Add the target entry:

   * choose a stable `id`
   * set a `url`
   * set a CSS `selector` that matches exactly one element containing only the numeric value
2. Validate with dry-run:

   ```bash
   python -m rate_monitor.cli \
     --targets config/targets.yml \
     --settings config/settings.yml \
     --output-dir output \
     --dry-run
   ```
3. Confirm:

   * `output/rates.csv` includes the target
   * `output/latest_stats.json` contains expected fields
4. Run without dry-run to persist to SQLite:

   ```bash
   python -m rate_monitor.cli \
     --targets config/targets.yml \
     --settings config/settings.yml \
     --output-dir output
   ```

### Recipe: Use a separate DB per environment

Use a different `db.path`:

```yaml
db:
  path: ./data/rates.prod.db
```

---

## Troubleshooting

### “No targets processed” / outputs are empty

Likely causes:

* You ran with the default `config/targets.example.yml`, which is commented out.
* Your `targets.yml` loaded as `null` (empty/comment-only).

Fix:

* Create `config/targets.yml` and pass it explicitly:

  ```bash
  python -m rate_monitor.cli --targets config/targets.yml
  ```

### “ParseError: selector not found”

Likely causes:

* Selector does not match in server-rendered HTML.
* The value is inserted by JavaScript after page load.

Fix:

* Inspect the raw HTML response and adjust selector.
* Prefer an authorized API endpoint where available, or a browser-based approach if permitted and required.

### Numbers parse incorrectly (commas/dots/currency)

The parser normalizes common formats such as:

* `1,234` → `1234.0`
* `1,234.56` → `1234.56`
* `1,23` → `1.23`

If your target uses a different format (e.g., additional text around the number), adjust the extraction source (selector) or extend the parser to extract numeric substrings.

### Slack does not send

Likely cause:

* Slack is not selectable via YAML in the current schema.

Fix:

* Use stdout alerts as-is, or implement the Slack enablement wiring described in [Slack Notifications](#slack-notifications).

### SQLite path errors

Likely causes:

* Parent directory does not exist.
* Missing permissions in the target folder.

Fix:

* Use a path under a writable directory (e.g., `./data/`) and ensure the folder exists.

---

## Security and Compliance Notes

* Do not commit real webhook URLs.
* Treat monitored URLs and extracted values as potentially sensitive business data.
* Respect target site Terms of Service and robots.txt where applicable.
* Configure your scheduler responsibly (avoid aggressive polling).
* Ensure you have authorization for any monitoring that involves restricted or private resources.

---

## Appendix: Full Reference Examples

### Example `targets.yml`

```yaml
targets:
  - id: usd_jpy
    name: USD/JPY (Example)
    url: https://example.com/rates/usd-jpy
    selector: ".rate-value"

  - id: eur_usd
    name: EUR/USD (Example)
    url: https://example.com/rates/eur-usd
    selector: ".rate-value"
```

### Example `settings.yml`

```yaml
db:
  path: ./data/rates.db

monitoring:
  interval_seconds: 300

alerts:
  enabled: true
  threshold: 5.0

slack:
  webhook_url: ""
  channel: "#alerts"
```
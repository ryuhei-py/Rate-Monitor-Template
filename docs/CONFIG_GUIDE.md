# Config Guide
This section explains how to configure the template while preserving the original guidance.

This document explains how to configure the **Rate Monitor Template** via:

- `config/targets.yml` – which rates to monitor.
- `config/settings.yml` – how the system behaves (DB path, windows, thresholds, Slack, etc.).
- `.env` – optional environment variables for secrets.

The goal is to make configuration **explicit, predictable, and easy to adapt** for different environments (local, staging, production, client-specific).

---

## 1. Overview
This section highlights the config-driven approach.

The template is fully **config-driven**:

- No hard-coded URLs or selectors in the core logic.
- All monitoring targets are defined in `targets.yml`.
- Global behavior (DB, analysis windows, thresholds, notifications) lives in `settings.yml`.
- Secrets (Slack webhook URL, etc.) belong in `.env` or environment variables, **not** in Git.

This separation allows you (or a client) to:

- Reuse the same code for multiple projects.
- Adjust behavior by editing YAML files.
- Keep secrets out of the repository.

---

## 2. `config/targets.yml`
This section explains how to define targets.

### 2.1 Purpose
`targets.yml` defines **what** you monitor:

- Each target is one “stream” of time-series data (e.g. USD/JPY rate, BTC/USDT price, product price).
- The CLI will iterate over all targets in this file on each run.

### 2.2 Structure
Basic structure:

```yaml
targets:
  - id: usd_jpy
    name: "USD/JPY"
    url: "https://example.com/usd-jpy"
    selector: "span.rate"

  - id: eur_usd
    name: "EUR/USD"
    url: "https://example.com/eur-usd"
    selector: "span.rate"
```

Top-level key:

targets:

Type: list of objects

Required: Yes

Each targets[] entry:

| Field    | Type | Required | Example                   | Description                                                              |
|----------|------|----------|---------------------------|--------------------------------------------------------------------------|
| id       | str  | Yes      | usd_jpy                   | Unique identifier for the target. Used as DB key and in logs/export.     |
| name     | str  | Yes      | "USD/JPY"                 | Human-readable name. Used for logging, notifications, and dashboards.    |
| url      | str  | Yes      | "https://example.com/usd" | The page from which we fetch the latest rate (HTTP GET).                 |
| selector | str  | Yes      | "span.rate-value"         | CSS selector used by the parser to find the element containing the rate. |

Note: The exact internal representation in code may use a TargetConfig dataclass, but conceptually these are the required fields.

### 2.3 Choosing id values
Best practices:

Use lowercase, snake_case IDs:

usd_jpy, btc_usdt, product_12345.

Keep them stable over time:

Renaming IDs effectively creates a “new time series” in the DB.

Avoid spaces and special characters:

These IDs may appear in filenames, logs, and JSON keys.

### 2.4 Choosing selector values
The selector must match the DOM structure of the target page. Examples:

Simple span:

HTML: <span class="rate">123.45</span>

Selector: "span.rate"

Nested elements:

HTML: <div id="price"><span class="value">123.45</span></div>

Selector: "#price span.value"

Table cell:

HTML: <table><tr><td class="value">123.45</td></tr></table>

Selector: "td.value"

Tips:

Use browser dev tools (F12 → Elements) to inspect the element and derive a stable selector.

Prefer IDs (#price) or specific class names (.rate-value) over very generic selectors.

Keep selectors simple and robust against minor layout changes.

### 2.5 Example: Product price monitoring
You can monitor product prices (not just FX):

```yaml
targets:
  - id: product_abc
    name: "Example Product"
    url: "https://shop.example.com/products/abc"
    selector: "span.product-price"
```

As long as the element’s text can be normalized into a numeric value (123.45, ¥123.45, etc.), the template will treat it as a generic “rate”.

---

## 3. config/settings.yml
This section explains system behavior configuration.

### 3.1 Purpose
settings.yml defines how the system behaves, including:

Where to store data (DB path),

How many days to consider for moving averages,

When to alert (percentage thresholds),

How to notify (Slack / stdout).

### 3.2 Structure
Typical example:

```yaml
db:
  path: "data/rates.sqlite3"

monitoring:
  window_days_short: 7
  window_days_long: 30

alerts:
  change_threshold_percent: 5.0

slack:
  enabled: false
  webhook_url: ""   # optional, can be populated from env
  channel: "#alerts"
```

Top-level sections:

| Section    | Description                                  |
|------------|----------------------------------------------|
| db         | Database configuration (SQLite file path).   |
| monitoring | Analysis window sizes (short vs long).       |
| alerts     | Thresholds controlling when alerts fire.     |
| slack      | Slack notification configuration (optional). |

#### 3.2.1 db section
```yaml
db:
  path: "data/rates.sqlite3"
```

Fields:

| Field | Type | Required | Example              | Description                                  |
|-------|------|----------|----------------------|----------------------------------------------|
| path  | str  | Yes      | "data/rates.sqlite3" | File path of the SQLite DB used by the tool. |

Notes:

The path can be relative (to project root) or absolute.

Ensure the parent directory (data/) exists or that your code creates it.

#### 3.2.2 monitoring section
```yaml
monitoring:
  window_days_short: 7
  window_days_long: 30
```

Fields:

| Field             | Type | Required | Example | Description                                               |
|-------------------|------|----------|---------|-----------------------------------------------------------|
| window_days_short | int  | Yes      | 7       | How many days to consider for the “short” moving average. |
| window_days_long  | int  | Yes      | 30      | How many days to consider for the “long” moving average.  |

Guidelines:

Choose windows that reflect the timescales you care about:

For FX: short = 3–7, long = 30 or 60.

For daily product prices: similar ranges often work.

If there is not enough data yet, the analysis layer should handle it gracefully (e.g. using available points or returning None for some averages).

#### 3.2.3 alerts section
```yaml
alerts:
  change_threshold_percent: 5.0
```

Fields:

| Field                    | Type  | Required | Example | Description                                                               |
|--------------------------|-------|----------|---------|---------------------------------------------------------------------------|
| change_threshold_percent | float | Yes      | 5.0     | Threshold (%). If abs(change) > threshold, the target is marked as alert. |

Notes:

The exact logic is implemented in analyzer.py:

Typically compares absolute percentage change vs. this threshold.

May consider either or both of short/long averages.

Choose thresholds based on volatility:

Highly volatile assets may need a higher threshold to avoid noise.

#### 3.2.4 slack section
```yaml
slack:
  enabled: false
  webhook_url: ""
  channel: "#alerts"
```

Fields:

| Field       | Type | Required | Example                                | Description                                                                 |
|-------------|------|----------|----------------------------------------|-----------------------------------------------------------------------------|
| enabled     | bool | Yes      | true / false                           | Whether to use Slack for notifications.                                     |
| webhook_url | str  | No*      | "https://hooks.slack.com/services/..." | Incoming webhook URL for Slack. Required if enabled: true.                  |
| channel     | str  | No       | "#alerts"                              | Channel name for documentation/logging (not always used by incoming hooks). |

Recommended pattern:

Keep webhook_url empty in version-controlled configs.

Load the actual value from .env or environment variables at runtime.

---

## 4. .env and environment variables
This section explains secret handling.

### 4.1 Purpose
The .env file (and environment variables in general) are used for:

Secrets (Slack webhook URLs).

Environment-specific overrides.

An example .env.example:

```env
# Slack integration (optional)
SLACK_WEBHOOK_URL=
SLACK_CHANNEL=#alerts
```

### 4.2 Using .env
Typical usage pattern (if implemented in your code):

Load .env at startup (e.g., using python-dotenv).

Read values from os.environ inside config.py or notifier.py.

Example (conceptual):

```python
import os

slack_webhook_from_env = os.getenv("SLACK_WEBHOOK_URL")

# Use env var if not provided in settings.yml
webhook_url = settings.slack.webhook_url or slack_webhook_from_env
```

Notes:

The exact logic depends on your implementation.

The guide recommends the pattern; the code should be adapted accordingly.

### 4.3 Environment-specific patterns
For multiple environments:

Use different .env files managed by deployment tools (not committed).

Set environment variables directly in:

systemd unit files,

container definitions,

CI/CD pipelines.

---

## 5. Example configurations
This section provides minimal and multi-target examples.

### 5.1 Minimal example (single FX pair, no Slack)
`config/targets.yml`:

```yaml
targets:
  - id: usd_jpy
    name: "USD/JPY"
    url: "https://example.com/usd-jpy"
    selector: "span.rate"
```

`config/settings.yml`:

```yaml
db:
  path: "data/rates.sqlite3"

monitoring:
  window_days_short: 7
  window_days_long: 30

alerts:
  change_threshold_percent: 5.0

slack:
  enabled: false
  webhook_url: ""
  channel: "#alerts"
```

`.env`:

```env
# Not required; Slack disabled.
```

### 5.2 Multiple targets + Slack alerts
`config/targets.yml`:

```yaml
targets:
  - id: usd_jpy
    name: "USD/JPY"
    url: "https://example.com/usd-jpy"
    selector: "span.rate"

  - id: btc_usdt
    name: "BTC/USDT"
    url: "https://example.com/btc-usdt"
    selector: "div.price span.value"
```

`config/settings.yml`:

```yaml
db:
  path: "/var/data/rate-monitor/rates.sqlite3"

monitoring:
  window_days_short: 3
  window_days_long: 30

alerts:
  change_threshold_percent: 3.0

slack:
  enabled: true
  webhook_url: ""   # real value from .env
  channel: "#rate-alerts"
```

`.env`:

```env
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/XXX/YYY/ZZZ
SLACK_CHANNEL=#rate-alerts
```

---

## 6. Validation and common pitfalls
This section lists validation expectations and common mistakes.

### 6.1 Validation
When config.py loads these files, it should:

Validate presence of required fields:

db.path, window_days_short, window_days_long, change_threshold_percent.

id, name, url, selector for each target.

Raise a ConfigError with a clear message when:

A required field is missing.

A value has an incorrect type (e.g. string instead of number).

From an operational standpoint, it’s good practice to:

Run the CLI once in --dry-run mode after changing configs.

Watch for any ConfigError or parse errors in the output/logs.

### 6.2 Common mistakes
Forgetting to copy example configs

Solution: cp config/targets.example.yml config/targets.yml and cp config/settings.example.yml config/settings.yml.

Using incorrect or unstable selectors

Solution: Use browser dev tools to confirm selectors. Re-test when the site layout changes.

Hardcoding secrets into YAML

Solution: Keep webhook_url empty in YAML; use .env or environment variables.

DB path pointing to a non-existent directory

Solution: Ensure the parent directory exists (e.g. data/), or handle directory creation in code.

---

## 7. Summary
This section summarizes the purpose of each config file.

config/targets.yml answers: What do we monitor? (IDs, names, URLs, selectors)

config/settings.yml answers: How do we monitor? (DB path, analysis windows, alert thresholds, notification channels)

.env answers: Where are the secrets? (Slack webhook, etc.)

Together, these configuration files make the Rate Monitor Template:

Easy to adapt to new projects and environments,

Safe to version-control (with secrets excluded),

And clear for clients or reviewers to understand and extend.
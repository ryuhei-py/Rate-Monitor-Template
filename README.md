# Rate Monitor Template
This section explains the purpose of the template and keeps the original introduction intact.

A reusable Python template for **daily price / rate monitoring**.

This repository provides a production-style skeleton for tracking any kind of time-series rate data (FX rates, crypto prices, product prices, interest rates, etc.), storing it in SQLite, analyzing changes against moving averages, and sending alerts (e.g. Slack) when thresholds are exceeded.

The design mirrors a real-world monitoring system: configurable targets, a small but clear layered architecture, automated tests, and a CLI entrypoint that can be scheduled via cron or Windows Task Scheduler.

---

## Features
This section lists the capabilities of the template while keeping the original bullet points.

- **Config-driven targets**
  - Define what to monitor (FX pairs, tickers, products, etc.) via YAML.
  - Per-target URL and CSS selector for extracting the latest rate.
- **SQLite time-series storage**
  - Simple `RateDatabase` abstraction on top of SQLite.
  - Stores `(target_id, timestamp, value)` with appropriate indexing.
- **Rate analysis & alerts**
  - Computes short / long moving averages over a configurable window.
  - Detects percentage change vs. those baselines.
  - Flags abnormal moves above a configurable threshold.
- **Notifications**
  - Pluggable notifier layer:
    - `StdoutNotifier` for simple console alerts.
    - `SlackNotifier` using incoming Webhooks (optional).
- **Exporters**
  - Export stored history to CSV.
  - Export latest stats to JSON for dashboards or downstream tools.
- **CLI-first design**
  - Single command to:
    - load config
    - fetch current rates
    - store to DB
    - analyze
    - export
    - notify.
- **Ready for CI / testing**
  - `pytest` test suite per module (config, db, analyzer, exporter, notifier, etc.).
  - GitHub Actions workflow skeleton (lint + tests) under `.github/workflows/`.

---

## Architecture overview
This section explains how the system is structured and preserves the original descriptions.

At a high level, the system is composed of the following layers:

- **Config layer (`config.py`)**
  - Loads YAML files (`targets.yml`, `settings.yml`) and validates them into structured config objects.
- **Fetching layer (`fetcher.py`)**
  - Responsible for HTTP GET requests with timeout, retries, and headers.
  - Provides a `Fetcher` class.
- **Parsing layer (`parser.py`)**
  - Given HTML and a CSS selector, extracts the numeric rate value.
  - Handles basic normalization (e.g. commas, currency symbols).
- **Storage layer (`db.py`)**
  - Encapsulates SQLite logic for inserting and retrieving time-series rate data.
- **Analysis layer (`analyzer.py`)**
  - Computes current value, short/long averages, percent changes, and whether conditions for alerting are met.
- **Export layer (`exporter.py`)**
  - Converts history and stats to CSV/JSON.
- **Notification layer (`notifier.py`)**
  - Delivers alerts via stdout or Slack.
- **CLI (`cli.py`)**
  - Wires everything together and exposes a single entrypoint for ad-hoc runs and scheduling.

For a more detailed explanation and diagrams, see `docs/architecture.md`.

---

## Quickstart
This section explains how to set up and run the project step by step.

### 1. Requirements
This subsection lists prerequisites for running the template.

- Python 3.11+
- Git
- (Optional but recommended) a virtual environment

### 2. Clone and set up
This subsection shows how to clone the repository and install dependencies.

# Clone repository
```bash
git clone https://github.com/ryuhei-py/Rate-Monitor-Template.git
cd Rate-Monitor-Template
```

# Create virtual environment
```bash
python -m venv .venv
```

# Activate on Windows
```bash
./.venv/Scripts/activate
```

# Activate on macOS / Linux (if applicable)
```bash
source .venv/bin/activate
```

# Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configuration
This subsection explains copying example configuration files.

# Copy example configs
```bash
cp config/targets.example.yml config/targets.yml
cp config/settings.example.yml config/settings.yml
cp .env.example .env
```

`config/targets.yml`  
Defines which rates you monitor (IDs, names, URLs, CSS selectors).

`config/settings.yml`  
Defines database location, monitoring windows, alert thresholds, and Slack settings.

`.env` (optional)  
Can store secrets like SLACK_WEBHOOK_URL.

See `docs/CONFIG_GUIDE.md` for field-by-field details.

### 4. Run the monitor (ad-hoc)
This subsection explains how to run the monitor once.

# Run the CLI
```bash
python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir sample_output
```

This will:

Load settings and targets.

Initialize the SQLite database and schema (if not yet created).

Fetch the current rate for each target.

Insert new measurements into the DB (unless --dry-run is used).

Analyze changes vs. configured windows (e.g. 7-day / 30-day averages).

Export:

CSV history → sample_output/rates.csv

JSON stats → sample_output/latest_stats.json

Send notifications if any target triggers an alert.

You can test the pipeline without modifying the database via:

# Run in dry-run mode
```bash
python -m rate_monitor.cli --dry-run
```

### Scheduling
This subsection explains how to schedule periodic runs.

This template is designed to be run periodically:

Linux / macOS – cron example

# Add cron entry
```cron
0 * * * * cd /path/to/Rate-Monitor-Template && \
/path/to/.venv/bin/python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir /path/to/output
```

Windows – Task Scheduler example

Command:

# PowerShell scheduled command
```powershell
powershell -Command "cd C:/path/to/Rate-Monitor-Template; `
  ./.venv/Scripts/python.exe -m rate_monitor.cli `
  --targets config/targets.yml `
  --settings config/settings.yml `
  --output-dir sample_output"
```

Additional notes and examples live in `src/rate_monitor/scheduler_stub.py` and `docs/operations.md`.

### Project structure
This subsection shows the reference directory layout.

Reference structure (simplified):

```text
Rate-Monitor-Template/
├─ src/
│  └─ rate_monitor/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ fetcher.py
│     ├─ parser.py
│     ├─ db.py
│     ├─ analyzer.py
│     ├─ exporter.py
│     ├─ notifier.py
│     ├─ scheduler_stub.py
│     └─ cli.py
│
├─ config/
│  ├─ targets.example.yml
│  └─ settings.example.yml
│
├─ tests/
│  ├─ test_config.py
│  ├─ test_db.py
│  ├─ test_fetcher.py
│  ├─ test_parser.py
│  ├─ test_analyzer.py
│  ├─ test_exporter.py
│  └─ test_notifier.py
│
├─ docs/
│  ├─ architecture.md
│  ├─ operations.md
│  ├─ testing.md
│  ├─ CONFIG_GUIDE.md
│  └─ SECURITY_AND_LEGAL.md
│
├─ sample_output/
│  └─ rates.sample.csv
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml
│
├─ README.md
├─ LICENSE
├─ .gitignore
├─ pyproject.toml
├─ requirements.txt
└─ .env.example
```

### Testing
This subsection explains how to run tests.

# Run the full test suite
```bash
pytest
```

Testing details and strategy are documented in `docs/testing.md`.

### Security & legal considerations
This subsection highlights compliance responsibilities.

This repository is a generic template and does not target any specific website or API.
When you adapt it to a real service, you are responsible for ensuring that your usage:

complies with the website’s Terms of Service,

respects robots.txt and rate limits,

complies with applicable laws and regulations.

See `docs/SECURITY_AND_LEGAL.md` for more guidance and examples.

### Related templates
This subsection lists related templates.

This template is part of a trio of reusable scraping / automation templates:

Template A – Product List Scraper Template

Template B – Rate Monitor Template (this repository)

Template C – Hybrid API + Scraping Collector Template

Together, they demonstrate a consistent architectural approach that can be adapted to a wide range of Upwork-style projects involving scraping, automation, and data integration.

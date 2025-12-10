# Operations
This section describes how to run, operate, and maintain the template, preserving the existing guidance.

This document describes how to **run, operate, and maintain** the Rate Monitor Template in real-world environments.

It covers:

- local development and ad-hoc runs,
- configuration management,
- database handling (initialize, backup, rotate, reset),
- scheduling on Linux/macOS (cron) and Windows (Task Scheduler),
- logging and basic monitoring,
- handling secrets and environment variables,
- simple upgrade and migration patterns.

The goal is to show how this template can be operated like a small production system, while staying lightweight and easy to understand.

---

## 1. Runtime environments
This section lists supported environments and requirements.

The template is designed to run in:

- **Local development environments**
  - Windows (PowerShell, Command Prompt)
  - macOS / Linux (bash/zsh)
- **Server environments**
  - A small VM, EC2 instance, or on-premise machine
  - Docker (optional, not required by default)
- **Scheduled tasks**
  - Cron (Linux/macOS)
  - Windows Task Scheduler

Requirements:

- Python **3.11+**
- SQLite (comes with Python’s standard library)
- Ability to schedule recurring commands (cron / Task Scheduler)

---

## 2. Local development and ad-hoc runs
This section explains setup and one-off runs.

### 2.1 Initial setup
This subsection shows how to clone and install dependencies.

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

# Activate on macOS / Linux
```bash
source .venv/bin/activate
```

# Install dependencies
```bash
pip install -r requirements.txt
```

### 2.2 Configuration files
This subsection explains copying example configuration files.

# Copy example configs
```bash
cp config/targets.example.yml config/targets.yml
cp config/settings.example.yml config/settings.yml
cp .env.example .env
```

Edit:

`config/targets.yml`

Add or modify targets entries (IDs, names, URLs, CSS selectors).

`config/settings.yml`

Set DB path, monitoring windows, alert thresholds, and Slack settings.

`.env`

Add secrets such as SLACK_WEBHOOK_URL if needed.

Field-level configuration details are documented in `docs/CONFIG_GUIDE.md`.

### 2.3 Running the monitor once (manual run)
This subsection shows how to run the CLI once.

# Run the CLI
```bash
python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir sample_output
```

This command will:

Load settings and targets.

Initialize a SQLite database (if it does not exist yet).

Fetch current HTML for each target.

Parse the latest rate values.

Insert new records into the database.

Analyze historical data and detect abnormal changes.

Export:

history → sample_output/rates.csv

stats → sample_output/latest_stats.json

Send alerts via stdout or Slack (depending on configuration).

### 2.4 Dry-run mode
This subsection shows how to run without DB writes.

# Run in dry-run mode
```bash
python -m rate_monitor.cli --dry-run
```

Dry-run will still:

perform HTTP requests,

parse values,

run analysis,

export stats/history (depending on implementation),

but will not call insert_rate() on the database.

---

## 3. Configuration management
This section explains how to manage configs across environments.

### 3.1 Files
`config/targets.yml`

List of monitoring targets.

`config/settings.yml`

Global behaviour (DB path, windows, thresholds, Slack config).

`.env`

Environment-specific secrets (Slack webhook, etc.)

### 3.2 Environment-specific configs
This subsection shows how to use per-environment files.

For multiple environments (dev/stage/prod), you can:

Use different config files:

`config/targets.dev.yml`, `config/settings.dev.yml`

`config/targets.prod.yml`, `config/settings.prod.yml`

Pass them to the CLI explicitly:

# Run with explicit configs
```bash
python -m rate_monitor.cli \
  --targets config/targets.prod.yml \
  --settings config/settings.prod.yml \
  --output-dir /var/data/rate-monitor/output
```

Use different `.env` files per environment

Managed by your deployment tool, not committed to Git.

### 3.3 Best practices
Never commit secrets (.env, real webhook URLs) to the repo.

Commit only *.example files, with placeholders and comments.

Keep environment-specific config in:

private repositories,

environment variables,

or deployment tools (Ansible, Terraform, etc.).

---

## 4. Database operations
This section explains how to initialize, back up, and reset the database.

The template uses a single SQLite database file (configurable via settings.yml).

### 4.1 Location and initialization
This subsection shows defaults and initialization.

The default location might look like:

```yaml
# config/settings.yml
db:
  path: "data/rates.sqlite3"
```

On first run, the CLI will:

Create the file if it does not exist.

Invoke RateDatabase.init_schema() to create the rates table and indexes.

You can also trigger schema initialization manually from a Python REPL:

# Initialize schema manually
```python
from rate_monitor.db import RateDatabase
from rate_monitor.config import load_settings

settings = load_settings("config/settings.yml")
db = RateDatabase(settings.db.path)
db.init_schema()
```

### 4.2 Backup
This subsection shows how to back up SQLite.

SQLite databases are simple files. For backup:

Stop the scheduled job (or ensure no ongoing writes).

Copy the file:

# Copy backup on Unix-like systems
```bash
cp data/rates.sqlite3 backups/rates.sqlite3-$(date +%Y%m%d%H%M%S)
```

On Windows (PowerShell):

# Copy backup on Windows
```powershell
Copy-Item data/rates.sqlite3 ("backups/rates.sqlite3-" + (Get-Date -Format "yyyyMMddHHmmss"))
```

Automate this via cron / Task Scheduler if needed (e.g., daily at night).

### 4.3 Rotation and retention
This subsection explains rotation practices.

For long-running systems:

Keep a rolling window of backups (e.g., last 7 or 30).

Use simple housekeeping scripts to delete older backup files.

SQLite itself can handle large databases, but for very long histories you can:

Periodically export old data to CSV and delete them from the DB, or

Switch to an external DB backend (see Architecture doc for hints).

### 4.4 Reset / rebuild
This subsection explains how to reset.

To reset the database:

Stop any scheduled jobs.

Move or delete the DB file:

# Remove database file
```bash
rm data/rates.sqlite3
```

Run the CLI again; init_schema() will recreate the schema on the next run.

Be careful: this removes all historical data.

---

## 5. Scheduling
This section explains how to schedule periodic runs.

The monitor is designed to be run periodically.
You can schedule it with cron (Linux/macOS) or Task Scheduler (Windows).

### 5.1 Linux / macOS – cron
This subsection shows cron usage.

Edit the crontab:

# Open crontab editor
```bash
crontab -e
```

Add an entry (example: run once every hour):

# Hourly cron entry
```cron
0 * * * * cd /path/to/Rate-Monitor-Template && \
/path/to/.venv/bin/python -m rate_monitor.cli \
  --targets config/targets.yml \
  --settings config/settings.yml \
  --output-dir /var/data/rate-monitor/output >> /var/log/rate-monitor.log 2>&1
```

Notes:

Adjust /path/to/Rate-Monitor-Template and .venv path as appropriate.

Redirect stdout / stderr to a log file for debugging (>> /var/log/... 2>&1).

You can choose other schedules, e.g.:

every 15 minutes: */15 * * * *

once a day at 09:00: 0 9 * * *

### 5.2 Windows – Task Scheduler
This subsection shows Task Scheduler usage.

Open Task Scheduler.

Create Basic Task:

Name: Rate Monitor

Trigger: e.g., “Daily” or “Every 1 hour”.

Action: “Start a program”

Program/script:

# Program path
```powershell
powershell.exe
```

Add arguments:

# PowerShell Task Scheduler command
```powershell
-Command "cd C:/path/to/Rate-Monitor-Template; `
  ./.venv/Scripts/python.exe -m rate_monitor.cli `
  --targets config/targets.yml `
  --settings config/settings.yml `
  --output-dir C:/path/to/output `
  >> C:/path/to/logs/rate-monitor.log 2>&1"
```

Ensure “Start in” is set to the project directory or handle it in the command.

As with cron, you can adjust frequency, log paths, and CLI options.

### 5.3 Docker (optional)
This subsection notes optional containerization.

Although not required, you can wrap the CLI into a Docker container:

Dockerfile (example outline):

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY . /app

RUN pip install --no-cache-dir -r requirements.txt

CMD ["python", "-m", "rate_monitor.cli", "--targets", "config/targets.yml", "--settings", "config/settings.yml", "--output-dir", "sample_output"]
```

Then schedule via:

host cron calling docker run, or

a container orchestrator (k8s CronJob, etc.).

This is beyond the scope of the template, but the architecture supports it.

---

## 6. Logging and basic monitoring
This section explains logging expectations.

### 6.1 Default logging
By default, the template uses:

print or simple logging to stdout for:

high-level progress,

alerts via StdoutNotifier,

error messages in the CLI.

When scheduled, redirect output to a log file as shown in the cron / Task Scheduler examples.

### 6.2 Integrating Python logging
For more formal logging:

Replace print statements in cli.py, notifier.py, etc. with Python’s logging module.

Configure log format and level at program start:

# Configure logging
```python
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
```

Send logs to:

a rotating file (using logging.handlers),

syslog,

or a centralized logging solution.

### 6.3 Health checks and sanity checks
Simple health indicators:

DB sanity:

get_history() returns data for active targets.

Alert sanity:

If no alerts for a long time, ensure the job is still running and history is being recorded.

Log review:

Periodically review log files for errors like FetchError, ParseError, NotificationError.

For more advanced setups, you can expose a tiny HTTP endpoint or write a heartbeat file, but that is out of scope for this template.

---

## 7. Secrets and environment variables
This section explains handling secrets.

Secrets (e.g. Slack webhook URLs) should not be committed.

### 7.1 .env file
.env.example documents expected variables:

```env
# Slack integration (optional)
SLACK_WEBHOOK_URL=
SLACK_CHANNEL=#alerts
```

In production:

Copy .env.example → .env.

Fill actual values in .env (but do not commit).

Use python-dotenv or your process manager to load these variables.

### 7.2 Environment variables (without .env)
Alternatively, set environment variables directly:

Linux/macOS:

# Export Slack vars on Unix-like systems
```bash
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/..."
export SLACK_CHANNEL="#alerts"
```

Windows (PowerShell):

# Export Slack vars on Windows
```powershell
$env:SLACK_WEBHOOK_URL = "https://hooks.slack.com/services/..."
$env:SLACK_CHANNEL = "#alerts"
```

Your configuration loading logic can then read from environment variables or interpolate them into settings.yml.

---

## 8. Upgrades and migrations
This section explains upgrade steps.

### 8.1 Code upgrades
To upgrade the template (e.g., pulling new commits):

Stop scheduled jobs.

Pull new code:

# Pull latest code
```bash
git pull origin main
```

If dependencies changed, reinstall:

# Reinstall requirements
```bash
pip install -r requirements.txt
```

Run tests:

# Run tests
```bash
pytest
```

Resume scheduled jobs.

### 8.2 Database schema changes
If you need to change the SQLite schema:

Add migrations inside RateDatabase.init_schema():

e.g., ALTER TABLE statements guarded by feature flags or version checks.

Back up the DB before schema changes.

Ensure tests cover the new behavior.

For complex migrations, consider:

Exporting data to CSV,

Dropping/re-creating the DB,

Re-importing data from CSV with a one-off script.

---

## 9. Operational runbook (quick reference)
This section summarizes quick actions.

### 9.1 Start / stop schedule
Start: enable cron / Task Scheduler entry.

Stop: disable cron / Task Scheduler entry.

### 9.2 Common issues
Network errors / HTTP 5xx

Check connectivity and target site status.

Confirm selectors have not changed.

Parse errors

Target HTML changed; inspect HTML and update selector or parser.

Slack notification failures

Verify webhook URL and channel.

Check network/firewall rules.

### 9.3 Quick recovery steps
Check latest log file for ERROR / Exception.

Run the CLI manually with --dry-run to see live behavior.

If DB is corrupted or unusable:

Restore from backup.

Or reset (delete and recreate) if historical data is non-critical.

---

## 10. Summary
This section summarizes operational posture.

Operationally, the Rate Monitor Template is intentionally simple:

It is just a Python CLI called on a schedule.

It uses a local SQLite file as its store.

It logs to stdout (redirectable to files).

It reads config from YAML and environment variables.

Despite this simplicity, the structure mirrors real production systems and is designed to be extended, hardened, and deployed to suit real Upwork or client projects.

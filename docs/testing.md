# Testing
This section describes the testing strategy and preserves existing guidance.

This document describes the testing strategy for the **Rate Monitor Template**.

The goals are:

- To keep the codebase **safe to modify** and **easy to refactor**.
- To demonstrate **professional engineering practices** (unit tests, clear structure, CI).
- To provide a **template** that can be reused and extended in client projects.

The test suite is built on **pytest** and focuses on **small, fast, isolated tests**.

---

## 1. Overview
This section introduces framework, scope, and philosophy.

### 1.1 Test framework
This subsection lists framework and structure.

- **Framework**: [pytest](https://docs.pytest.org/)
- **Location**: `tests/` directory (mirrors `src/rate_monitor/` structure)
- **Style**:
  - Function-based tests (`test_...` functions).
  - Use of fixtures (e.g. `tmp_path`, custom fixtures in `conftest.py`).
  - Extensive use of mocking for:
    - `requests.get` / `requests.post`
    - database connections (when appropriate)
    - CLI integration

### 1.2 What we test
This subsection lists coverage areas.

- **Config** loading and validation
- **DB** schema and basic CRUD behavior
- **Fetcher** retry and error handling
- **Parser** correctness for various HTML/number formats
- **Analyzer** logic (moving averages, thresholds, alert decisions)
- **Exporter** output correctness (CSV / JSON)
- **Notifier** behavior (stdout and Slack)
- **CLI** argument parsing and orchestration (via mocks, focused on behavior not I/O details)

### 1.3 Testing philosophy
This subsection summarizes guiding principles.

- Prefer **small, focused tests** over large integration tests.
- Keep each test **readable** and **self-explanatory**.
- Use **mocking** to isolate external dependencies (network, Slack, etc.).
- Ensure tests can run quickly as part of **CI** on each push / PR.

---

## 2. Running tests
This section explains how to run tests locally with examples.

### 2.1 Local execution
This subsection shows basic commands.

# Run all tests
```bash
pytest
```

This will:

Discover all test files matching tests/test_*.py.

Execute them using the default pytest configuration.

You can run a single file:

# Run one file
```bash
pytest tests/test_analyzer.py
```

Or a single test function:

# Run one test
```bash
pytest tests/test_analyzer.py::test_alert_triggered_when_threshold_exceeded
```

### 2.2 Test options (useful flags)
This subsection lists useful pytest flags.

Some useful pytest options:

- -v – verbose output (shows each test name)
- -q – quiet mode
- -x – stop on first failure
- -k <expression> – run tests matching expression (e.g. -k "db and not slow")

Examples:

# Verbose run
```bash
pytest -v
```

# Filter by expression
```bash
pytest -k "fetcher"
```

# Stop on first failure
```bash
pytest -x
```

### 2.3 Code coverage (optional)
This subsection notes optional coverage.

If you choose to add coverage (e.g., using pytest-cov), you can run:

# Run coverage
```bash
pytest --cov=rate_monitor --cov-report=term-missing
```

This is not required by the template, but it is a common extension in production systems.

---

## 3. Test organization
This section explains test layout.

The tests/ directory mirrors the main code modules:

```text
tests/
├─ conftest.py
├─ test_config.py
├─ test_db.py
├─ test_fetcher.py
├─ test_parser.py
├─ test_analyzer.py
├─ test_exporter.py
├─ test_notifier.py
└─ test_cli.py        # optional / lightweight
```

### 3.1 conftest.py
This subsection explains fixtures.

Used to define reusable fixtures:

Example fixtures:

A temporary YAML configuration (written into tmp_path).

Temporary SQLite database paths.

Dummy TargetConfig and Settings objects.

Mock RateStats instances.

By centralizing fixtures in conftest.py, tests remain concise and focused.

---

## 4. Module-specific tests
This section lists module-specific expectations.

### 4.1 Config (test_config.py)
Goal: Ensure that configuration is loaded and validated correctly.

Typical tests:

test_load_settings_valid_yaml

Write a minimal valid YAML to tmp_path / "settings.yml" and load it.

Assert fields (DB path, monitoring windows, alert threshold, Slack settings).

test_load_targets_valid_yaml

Write a YAML file with multiple targets.

Assert that:

load_targets() returns the correct number of TargetConfig objects.

id, name, url, selector are parsed correctly.

test_load_settings_missing_required_field_raises

Omit a required field (e.g. db.path).

Assert that ConfigError is raised with a helpful message.

Key points:

Use temporary files (tmp_path) instead of real config files.

Keep tests independent from actual config/*.example.yml.

### 4.2 Database (test_db.py)
Goal: Verify that RateDatabase handles schema creation and basic time-series operations.

Typical tests:

test_init_schema_creates_table

Use an in-memory DB (:memory:) or tmp_path / "test.sqlite3".

Call init_schema().

Query SQLite metadata to assert that the rates table exists.

test_insert_and_get_history_round_trip

Insert a few records with different timestamps for a given target_id.

Call get_history(target_id, days=N).

Assert that the returned data matches what was inserted (filtering by date).

test_get_history_filters_by_days

Insert older and newer records.

Call get_history(..., days=7) and confirm that older records are excluded.

Key points:

Tests should be isolated—no reliance on real data/rates.sqlite3.

Consider using tmp_path for DB files and deleting them after tests.

### 4.3 Fetcher (test_fetcher.py)
Goal: Confirm behavior around HTTP requests, retries, and errors.

Typical tests (using monkeypatch or unittest.mock):

test_fetcher_successful_request

Mock requests.get to return a 200 response with test HTML.

Assert that Fetcher.get() returns the expected text.

test_fetcher_retries_on_5xx

Mock requests.get to raise or return 500 on first calls, then 200.

Assert:

It retries up to max_retries.

It eventually returns the 200 body.

test_fetcher_does_not_retry_on_4xx

Mock requests.get to return a 404.

Assert that it does not retry and raises FetchError.

test_fetcher_sets_timeout_and_headers

Verify that requests.get is called with the configured timeout and headers.

Key points:

No real network calls occur in tests.

Use mocking to simulate different HTTP conditions.

### 4.4 Parser (test_parser.py)
Goal: Validate that HTML is parsed correctly into numeric values.

Typical tests:

test_parse_simple_number

HTML: <span class="rate">123.45</span>

Expect 123.45 as a float.

test_parse_number_with_comma

HTML: <span class="rate">123,45</span>

Expect 123.45 (comma replaced with dot).

test_parse_currency_symbol

HTML: <span class="rate">\123.45</span>

Expect 123.45 (currency symbol stripped).

test_parse_missing_element_raises_error

HTML without the target selector.

Expect ParseError with a descriptive message.

Key points:

Do not fetch real pages.

Embed small HTML snippets directly in the tests.

### 4.5 Analyzer (test_analyzer.py)
Goal: Ensure that moving averages, percentage changes, and alert decisions are correct.

Typical tests:

test_analyzer_no_values_returns_no_alert

Input: empty history list.

Expect current=None, all averages None, should_alert=False.

test_analyzer_small_change_no_alert

Input: values where the change vs. short/long averages is below threshold.

Expect should_alert=False.

test_analyzer_large_change_triggers_alert

Input: values with obvious spike.

Expect should_alert=True and a reason explaining which threshold was crossed.

test_analyzer_handles_short_history

Input: fewer points than window_long.

Confirm that long average is computed only from available data, or remains None depending on implementation.

Key points:

Tests should be numeric and deterministic.

Clearly document threshold behavior in tests (e.g. “strictly greater than threshold triggers alert”).

### 4.6 Exporter (test_exporter.py)
Goal: Confirm that CSV and JSON outputs are structured correctly.

Typical tests (using tmp_path):

test_export_history_to_csv

Provide a small set of rows (timestamp_iso, target_id, value).

Write to a temp file.

Read it back and assert:

The header row (timestamp,target_id,value).

Row count and cell values.

test_export_stats_to_json

Create several RateStats instances with test data.

Export to JSON.

Load the file and assert keys/values for each stats object.

Key points:

Focus on schema correctness, not formatting aesthetics.

Be explicit about types (string vs number).

### 4.7 Notifier (test_notifier.py)
Goal: Verify that notifications are sent in the right conditions and format.

Typical tests:

test_stdout_notifier_prints_on_alert

Create a RateStats with should_alert=True.

Use io.StringIO as the stream for StdoutNotifier.

Assert that output contains target ID and relevant values.

test_stdout_notifier_silent_when_no_alert

should_alert=False.

Assert that nothing is written.

test_slack_notifier_calls_webhook_when_alert

Mock requests.post.

should_alert=True.

Assert:

requests.post called once with the configured webhook URL.

Payload contains key stats.

test_slack_notifier_skips_when_no_alert

should_alert=False.

Assert requests.post is not called.

test_slack_notifier_raises_on_http_error

Mock requests.post to return a non-2xx response.

Expect NotificationError.

Key points:

No real Slack calls.

Tests express clearly when we send notifications and what happens on error.

### 4.8 CLI (test_cli.py)
Goal: Light, high-level checks of CLI behavior, without exercising full I/O.

Because CLI orchestration connects all layers, we keep tests:

Small.

Based on mocking internal components.

Typical tests:

test_cli_parses_arguments

Use monkeypatch to override sys.argv.

Invoke main() and assert that it reads the custom paths.

test_cli_dry_run_does_not_insert_into_db

Mock RateDatabase.insert_rate.

Run CLI with --dry-run.

Assert that insert_rate is not called.

test_cli_uses_slack_notifier_when_enabled

Mock SlackNotifier and StdoutNotifier.

Use settings that enable Slack.

Assert that CLI chooses Slack.

Key points:

Avoid real HTTP, DB, or file I/O.

Use mocks to assert the wiring is correct.

---

## 5. Continuous integration (CI)
This section notes CI expectations.

### 5.1 GitHub Actions workflow
The repository includes a skeleton workflow under:

```text
.github/workflows/ci.yml
```

A typical configuration (simplified) might:

Run on:

push to main

pull_request to main

Steps:

Check out the repository.

Set up Python (3.11).

Install dependencies.

Run ruff (linting).

Run pytest (tests).

This ensures that:

New changes pass tests before being merged.

Linting keeps style and potential issues under control.

### 5.2 Local vs CI
Locally:

You can run pytest + ruff manually.

In CI:

The workflow ensures the same commands are run on every push.

This demonstrates to clients that you follow a modern CI workflow.

---

## 6. Extending the test suite
This section suggests extensions.

When adapting this template to real projects, you can extend tests in the following ways:

Integration tests

Spin up a temporary environment using real configs.

Use a stable test site or a local mock server.

Property-based tests

For numeric calculations in analyzer.py, use tools like hypothesis to explore edge cases.

Performance tests

Benchmark get_history and analysis functions with larger datasets.

End-to-end smoke tests

Execute CLI in a temporary directory with fake targets, verifying that it:

Creates a DB,

Writes CSV/JSON,

Exits successfully.

The current suite is intentionally focused on unit tests, as that is the most portable and template-friendly approach.

---

## 7. Summary
This section summarizes the testing approach.

The Rate Monitor Template includes a structured, pytest-based test suite.

Each module has its own dedicated test file with isolated tests.

The suite is designed to run quickly, locally and in CI.

Tests are crafted to demonstrate:

Correctness,

Robustness to errors,

And professional engineering practices.

By following and extending this testing approach, you can confidently evolve the template into a production-ready monitoring solution for real-world client projects.

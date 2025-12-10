"""Lightweight tests for scheduler stub helpers."""

from rate_monitor import scheduler_stub


def test_cron_example_contains_cron_syntax() -> None:
    result = scheduler_stub.cron_example()
    assert "cron" in result or result.startswith("0 ")


def test_windows_task_scheduler_example_mentions_powershell() -> None:
    result = scheduler_stub.windows_task_scheduler_example()
    assert "powershell" in result.lower()

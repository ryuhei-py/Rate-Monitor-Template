"""
This module documents how to schedule the rate monitor in production.

It is intentionally minimal and does not depend on any scheduler library.
"""


def cron_example() -> str:
    """
    Return an example cron entry to run the CLI every hour.
    """
    return "0 * * * * cd /path/to/Rate-Monitor-Template && .venv/bin/python -m rate_monitor.cli"


def windows_task_scheduler_example() -> str:
    """
    Return a brief description of how to register a scheduled task on Windows.
    """
    return (
        "Use Task Scheduler to create a basic task that runs:\n"
        '  powershell -Command "cd C:\\path\\to\\Rate-Monitor-Template; '
        '.\\.venv\\Scripts\\python.exe -m rate_monitor.cli"'
    )

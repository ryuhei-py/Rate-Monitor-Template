"""Smoke tests for the initial project skeleton.

These tests only exist to keep CI green before real tests are implemented.
"""

def test_smoke_placeholder() -> None:
    """A placeholder test that always passes.

    This ensures pytest collects at least one test so CI does not fail with
    exit code 5 ("no tests collected").
    """
    assert True

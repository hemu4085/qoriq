"""
Regression test: ensure overall quality after fixes is not lower than before.

This test uses scripts/diagnose_quality.py --json to produce machine-readable
metrics. If your CI runs with the repo root as the working directory this will
work as-is.
"""
import subprocess
import json
import os
import sys
import pytest

ROOT = os.path.dirname(os.path.dirname(__file__))
FIXTURES_DIR = os.path.join(ROOT, "tests", "fixtures")
BEFORE = os.path.join(FIXTURES_DIR, "before.csv")
AFTER = os.path.join(FIXTURES_DIR, "after.csv")

def _run_diagnose(before_csv, after_csv):
    # Run the diagnostic script installed in the repo
    proc = subprocess.run(
        [sys.executable, os.path.join("scripts", "diagnose_quality.py"), before_csv, after_csv, "--json"],
        capture_output=True,
        text=True,
        check=False
    )

    if proc.returncode != 0:
        pytest.fail(f"diagnose_quality.py failed (rc={proc.returncode}):\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")

    return json.loads(proc.stdout)

def test_quality_does_not_decrease():
    result = _run_diagnose(BEFORE, AFTER)
    assert result["quality_after"] >= result["quality_before"], (
        f"quality decreased: before={result['quality_before']} after={result['quality_after']}"
    )
"""
Regression test for DQ score quality.

This test ensures that applying fixes does not reduce the overall Data Quality score.
It uses the diagnose_quality.py script to compare quality_before and quality_after,
and asserts that quality_after >= quality_before.
"""
import subprocess
import json
import sys
from pathlib import Path



def test_quality_regression():
    """
    Test that quality score does not decrease after applying fixes.
    
    This is a regression test for the issue where the fixer was introducing
    empty strings and None values that reduced completeness and safety scores.
    """
    # Paths to test fixtures
    fixtures_dir = Path(__file__).parent / "fixtures"
    before_csv = fixtures_dir / "before.csv"
    after_csv = fixtures_dir / "after.csv"
    
    # Ensure fixtures exist
    assert before_csv.exists(), f"Missing test fixture: {before_csv}"
    assert after_csv.exists(), f"Missing test fixture: {after_csv}"
    
    # Run diagnose_quality.py with --json flag
    script_path = Path(__file__).parent.parent / "scripts" / "diagnose_quality.py"
    result = subprocess.run(
        [sys.executable, str(script_path), str(before_csv), str(after_csv), "--json"],
        capture_output=True,
        text=True,
        check=True
    )
    
    # Parse JSON output
    summary = json.loads(result.stdout)
    
    # Extract scores
    quality_before = summary["quality_before"]
    quality_after = summary["quality_after"]
    completeness_before = summary["completeness_before"]
    completeness_after = summary["completeness_after"]
    safety_before = summary["safety_before"]
    safety_after = summary["safety_after"]
    
    # Assert that quality scores do not decrease
    # Allow small floating-point tolerance
    tolerance = 1e-4
    
    assert quality_after >= quality_before - tolerance, (
        f"Overall quality score decreased: {quality_before:.4f} -> {quality_after:.4f}"
    )
    
    assert completeness_after >= completeness_before - tolerance, (
        f"Completeness score decreased: {completeness_before:.4f} -> {completeness_after:.4f}"
    )
    
    assert safety_after >= safety_before - tolerance, (
        f"Safety score decreased: {safety_before:.4f} -> {safety_after:.4f}"
    )
    
    # Print summary for visibility
    print("\n✓ Quality score check passed:")
    print(f"  Overall: {quality_before:.4f} -> {quality_after:.4f} ({quality_after - quality_before:+.4f})")
    print(f"  Completeness: {completeness_before:.4f} -> {completeness_after:.4f} ({completeness_after - completeness_before:+.4f})")
    print(f"  Safety: {safety_before:.4f} -> {safety_after:.4f} ({safety_after - safety_before:+.4f})")

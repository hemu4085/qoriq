"""
Regression test to ensure data quality scores do not decrease after applying fixes.

This test addresses the issue where the fixer was inadvertently reducing completeness
and safety scores by converting empty strings and unparseable values to NaN/NaT.
"""
import json
import subprocess
import sys
from pathlib import Path

import pytest
import pandas as pd

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from fixer import generate_naive_clean_with_summary  # noqa: E402
from quality import compute_quality_scores  # noqa: E402


def test_quality_does_not_decrease_after_fixer():
    """
    Test that applying the fixer does not reduce quality scores.
    
    This is a regression test for the issue where empty strings and malformed
    dates were being converted to NaN/NaT, reducing completeness and safety scores.
    """
    # Load the before fixture
    fixture_path = Path(__file__).parent / "fixtures" / "before.csv"
    df_before = pd.read_csv(fixture_path)
    
    # Compute quality before fixes
    quality_before = compute_quality_scores(df_before)
    
    # Apply fixer
    df_after, summary, changes_df, removed_rows = generate_naive_clean_with_summary(df_before, [])
    
    # Compute quality after fixes
    quality_after = compute_quality_scores(df_after)
    
    # Assert that quality scores did not decrease
    completeness_before = quality_before['components']['completeness']['score']
    completeness_after = quality_after['components']['completeness']['score']
    assert completeness_after >= completeness_before, (
        f"Completeness decreased: {completeness_before} -> {completeness_after}"
    )
    
    safety_before = quality_before['components']['safety']['score']
    safety_after = quality_after['components']['safety']['score']
    assert safety_after >= safety_before, (
        f"Safety decreased: {safety_before} -> {safety_after}"
    )
    
    overall_before = quality_before['overall_score']
    overall_after = quality_after['overall_score']
    assert overall_after >= overall_before, (
        f"Overall quality decreased: {overall_before} -> {overall_after}"
    )


def test_diagnose_quality_script_json_output():
    """
    Test that diagnose_quality.py script works with --json flag.
    
    This ensures the script can be used for automated testing and monitoring.
    """
    fixture_path = Path(__file__).parent / "fixtures" / "before.csv"
    script_path = Path(__file__).parent.parent / "scripts" / "diagnose_quality.py"
    
    # Run the script with --json flag
    result = subprocess.run(
        ["python", str(script_path), str(fixture_path), "--json"],
        capture_output=True,
        text=True
    )
    
    assert result.returncode == 0, f"Script failed: {result.stderr}"
    
    # Parse JSON output
    try:
        quality_data = json.loads(result.stdout)
    except json.JSONDecodeError as e:
        pytest.fail(f"Failed to parse JSON output: {e}\nOutput: {result.stdout}")
    
    # Verify structure
    assert "overall_score" in quality_data
    assert "components" in quality_data
    assert "completeness" in quality_data["components"]
    assert "safety" in quality_data["components"]
    

def test_fixer_preserves_unparseable_dates():
    """
    Test that the fixer preserves unparseable date strings instead of converting to NaN.
    
    This is a specific test for the _safe_coerce_dates function.
    """
    # Create a test dataframe with unparseable dates
    df = pd.DataFrame({
        "date_col": ["2024-01-15", "invalid-date", "", None, "2024-02-20"],
        "value": [1, 2, 3, 4, 5]
    })
    
    # Apply fixer
    df_after, _, _, _ = generate_naive_clean_with_summary(df, [])
    
    # Check that valid dates are standardized
    assert df_after.loc[0, "date_col"] == "2024-01-15"
    assert df_after.loc[4, "date_col"] == "2024-02-20"
    
    # Check that unparseable dates are preserved (not converted to NaN)
    assert df_after.loc[1, "date_col"] == "invalid-date"
    
    # Empty strings and None may be converted to NaN, which is acceptable
    # since they represent missing values


def test_empty_strings_normalized_in_scoring():
    """
    Test that empty strings are normalized to NaN during quality scoring.
    
    This ensures consistent scoring regardless of how missing values are represented.
    """
    # Create two dataframes - one with empty strings, one with NaN
    df_empty = pd.DataFrame({
        "col1": ["a", "b", "", "d"],
        "col2": [1, 2, 3, 4]
    })
    
    df_nan = pd.DataFrame({
        "col1": ["a", "b", None, "d"],
        "col2": [1, 2, 3, 4]
    })
    
    # Compute quality scores
    quality_empty = compute_quality_scores(df_empty)
    quality_nan = compute_quality_scores(df_nan)
    
    # Scores should be the same since empty strings are normalized to NaN
    assert quality_empty['components']['completeness']['score'] == quality_nan['components']['completeness']['score']


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

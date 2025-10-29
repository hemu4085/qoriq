"""
Regression test for data quality score degradation after applying fixes.

Tests that the fixer does not reduce overall data quality scores by introducing
additional NaN values during date standardization or other transformations.
"""
import pandas as pd
from pathlib import Path

from src.quality import compute_quality_scores
from src.validator import detect_issues
from src.fixer import generate_naive_clean_with_summary


FIXTURES_DIR = Path(__file__).parent / "fixtures"


def test_quality_no_degradation_on_invalid_dates():
    """
    Test that applying fixes does not degrade data quality scores.
    
    The fixer should preserve invalid date values rather than converting them
    to NaN, which would reduce completeness and safety scores.
    """
    # Load fixture with 100% complete data (no NaN values)
    # but includes some invalid date strings
    df_before = pd.read_csv(FIXTURES_DIR / "before.csv")
    
    # Verify fixture is 100% complete
    assert df_before.isna().sum().sum() == 0, "Fixture should have no missing values"
    
    # Compute quality before fixes
    quality_before = compute_quality_scores(df_before)
    
    # Apply fixes
    issues = detect_issues(df_before, missing_threshold=0.2)
    cleaned_df, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(
        df_before, issues
    )
    
    # Compute quality after fixes
    quality_after = compute_quality_scores(cleaned_df)
    
    # Assert no quality degradation
    overall_delta = quality_after['overall_score'] - quality_before['overall_score']
    completeness_delta = (quality_after['components']['completeness']['score'] - 
                         quality_before['components']['completeness']['score'])
    safety_delta = (quality_after['components']['safety']['score'] - 
                   quality_before['components']['safety']['score'])
    
    # Overall quality should not degrade
    assert quality_after['overall_score'] >= quality_before['overall_score'], (
        f"Overall quality degraded: {quality_before['overall_score']:.4f} -> "
        f"{quality_after['overall_score']:.4f} (Δ {overall_delta:.4f})"
    )
    
    # Completeness should not decrease (fixes should not introduce new NaN values)
    assert quality_after['components']['completeness']['score'] >= quality_before['components']['completeness']['score'], (
        f"Completeness degraded: {quality_before['components']['completeness']['score']:.4f} -> "
        f"{quality_after['components']['completeness']['score']:.4f} (Δ {completeness_delta:.4f})"
    )
    
    # Safety should not decrease significantly
    assert quality_after['components']['safety']['score'] >= quality_before['components']['safety']['score'], (
        f"Safety degraded: {quality_before['components']['safety']['score']:.4f} -> "
        f"{quality_after['components']['safety']['score']:.4f} (Δ {safety_delta:.4f})"
    )


def test_fixer_preserves_invalid_dates_as_strings():
    """
    Test that the fixer preserves unparseable date strings rather than converting to NaN.
    
    This is the core fix: when a date cannot be parsed, keep the original value
    instead of replacing it with None/NaN.
    """
    # Create a dataframe with invalid dates
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'expected_close': ['2023-01-15', 'invalid-date', '2023-03-10']
    })
    
    # Verify no missing values before
    assert df.isna().sum().sum() == 0
    
    # Apply fixes
    issues = detect_issues(df, missing_threshold=0.2)
    cleaned_df, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(df, issues)
    
    # Check that invalid date is preserved as string, not converted to NaN
    assert cleaned_df.loc[1, 'expected_close'] == 'invalid-date', (
        "Invalid date should be preserved as original string"
    )
    
    # No new NaN values should be introduced
    nan_count_before = df.isna().sum().sum()
    nan_count_after = cleaned_df.isna().sum().sum()
    assert nan_count_after == nan_count_before, (
        f"Fixer introduced {nan_count_after - nan_count_before} new NaN values"
    )


def test_fixer_normalizes_parseable_dates():
    """
    Test that the fixer correctly normalizes parseable dates to YYYY-MM-DD format.
    Note: The fixer tries dayfirst=False first, then dayfirst=True for unparsed dates.
    Mixed formats in the same column may not all parse if they require different settings.
    """
    df = pd.DataFrame({
        'id': [1, 2, 3, 4],
        'expected_close': ['2023-01-15', '15/03/2023', '2023-06-20', '20/07/2023']
    })
    
    issues = detect_issues(df, missing_threshold=0.2)
    cleaned_df, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(df, issues)
    
    # ISO dates should remain normalized
    assert cleaned_df.loc[0, 'expected_close'] == '2023-01-15'
    # DD/MM/YYYY format should be parsed with dayfirst fallback
    assert cleaned_df.loc[1, 'expected_close'] == '2023-03-15'
    # ISO dates should remain normalized
    assert cleaned_df.loc[2, 'expected_close'] == '2023-06-20'
    # DD/MM/YYYY format should be parsed with dayfirst fallback
    assert cleaned_df.loc[3, 'expected_close'] == '2023-07-20'


def test_diagnose_quality_script_execution():
    """
    Test that the diagnose_quality.py script runs successfully on fixtures.
    """
    import subprocess
    import sys
    
    # Run the diagnose script
    result = subprocess.run(
        [sys.executable, "scripts/diagnose_quality.py", str(FIXTURES_DIR / "before.csv")],
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent
    )
    
    # Script should exit with code 0 (quality maintained or improved)
    assert result.returncode == 0, (
        f"diagnose_quality.py failed with code {result.returncode}\n"
        f"stdout: {result.stdout}\n"
        f"stderr: {result.stderr}"
    )
    
    # Check that output contains expected sections
    assert "BEFORE" in result.stdout
    assert "AFTER" in result.stdout
    assert "Quality Change Analysis" in result.stdout

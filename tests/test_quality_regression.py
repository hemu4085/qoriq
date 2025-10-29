"""
Regression test to ensure that applying fixes does not reduce overall data quality score.

This test addresses the issue where the fixer was introducing NaN values for unparseable
dates, causing completeness and safety scores to drop unexpectedly.
"""
import sys
from pathlib import Path
import pandas as pd
import pytest

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quality import compute_quality_scores
from src.validator import detect_issues
from src.fixer import generate_naive_clean_with_summary


def test_quality_score_does_not_decrease_after_fixes():
    """
    Test that applying fixes maintains or improves the overall quality score.
    
    This is a regression test for the issue where the fixer was introducing
    NaN/NaT values for unparseable dates, causing the completeness score to drop.
    """
    # Load the test fixture
    fixture_path = Path(__file__).parent / "fixtures" / "before.csv"
    df_before = pd.read_csv(fixture_path)
    
    # Compute quality before fixes
    quality_before = compute_quality_scores(df_before)
    
    # Detect issues
    issues = detect_issues(df_before)
    
    # Apply fixes
    df_after, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(
        df_before, issues
    )
    
    # Compute quality after fixes
    quality_after = compute_quality_scores(df_after)
    
    # Assert overall quality does not decrease
    assert quality_after["overall_score"] >= quality_before["overall_score"], (
        f"Overall quality score decreased after fixes: "
        f"{quality_before['overall_score']} -> {quality_after['overall_score']}"
    )
    
    # Assert completeness does not decrease (this was the main issue)
    completeness_before = quality_before["components"]["completeness"]["score"]
    completeness_after = quality_after["components"]["completeness"]["score"]
    assert completeness_after >= completeness_before, (
        f"Completeness score decreased after fixes: "
        f"{completeness_before} -> {completeness_after}"
    )
    
    # Log the results for debugging
    print(f"\nQuality before: {quality_before['overall_percent']:.2f}%")
    print(f"Quality after:  {quality_after['overall_percent']:.2f}%")
    print(f"Difference:     {quality_after['overall_percent'] - quality_before['overall_percent']:+.2f}%")


def test_fixer_does_not_introduce_nan_for_unparseable_dates():
    """
    Test that the fixer preserves original values for dates that cannot be parsed,
    rather than replacing them with NaN/None.
    """
    # Create a simple test dataframe with unparseable dates
    df = pd.DataFrame({
        "id": [1, 2, 3],
        "date_col": ["2024-01-15", "not-a-date", "invalid"],
        "name": ["Alice", "Bob", "Charlie"]
    })
    
    # Detect issues (should detect date_partial_parse)
    issues = detect_issues(df)
    
    # Apply fixes
    df_fixed, _, _, _ = generate_naive_clean_with_summary(df, issues)
    
    # Check that no NaN values were introduced
    assert df_fixed["date_col"].notna().all(), (
        "Fixer introduced NaN values for unparseable dates"
    )
    
    # Check that the successfully parsed date is standardized
    assert df_fixed["date_col"].iloc[0] == "2024-01-15", (
        "Valid date should be standardized to YYYY-MM-DD format"
    )
    
    # Check that unparseable dates are preserved (not converted to None)
    # They should remain as the original values
    for i in [1, 2]:  # Indices with unparseable dates
        assert df_fixed["date_col"].iloc[i] is not None and df_fixed["date_col"].iloc[i] != "", (
            f"Unparseable date at index {i} should be preserved, not set to None or empty string"
        )


def test_quality_scoring_treats_empty_strings_and_nan_consistently():
    """
    Test that the quality scoring module treats empty strings and NaN values
    consistently by normalizing them before scoring.
    """
    # Create two dataframes: one with NaN, one with empty strings
    df_with_nan = pd.DataFrame({
        "col1": [1, 2, None],
        "col2": ["a", "b", None]
    })
    
    df_with_empty = pd.DataFrame({
        "col1": [1, 2, None],
        "col2": ["a", "b", ""]
    })
    
    # Compute quality scores
    quality_nan = compute_quality_scores(df_with_nan)
    quality_empty = compute_quality_scores(df_with_empty)
    
    # The completeness scores should be the same since empty strings
    # should be normalized to NaN before scoring
    assert quality_nan["components"]["completeness"]["score"] == quality_empty["components"]["completeness"]["score"], (
        "Empty strings and NaN should be treated consistently in completeness scoring"
    )


if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"])

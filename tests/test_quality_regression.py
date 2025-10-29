"""
Regression test for data quality score after applying fixes.

This test ensures that applying fixes does not reduce the overall quality score.
The fixer should either maintain or improve the overall quality score.
"""
import pandas as pd
from pathlib import Path

from src.quality import compute_quality_scores
from src.fixer import generate_naive_clean_with_summary
from src.validator import detect_issues


def test_quality_regression_with_fixtures():
    """Test that quality score does not regress after applying fixes using fixture data"""
    # Load the test fixture
    fixture_path = Path(__file__).parent / 'fixtures' / 'before.csv'
    df = pd.read_csv(fixture_path, keep_default_na=False, na_values=['NA', 'N/A', 'null', 'None'])
    
    # Validate to get issues
    issues = detect_issues(df)
    
    # Compute quality before fixes
    quality_before = compute_quality_scores(df, {}, issues)
    
    # Apply fixes
    cleaned_df, summary, changes_df, removed_df = generate_naive_clean_with_summary(df, issues)
    
    # Compute quality after fixes
    quality_after = compute_quality_scores(cleaned_df, {}, [])
    
    # Assert that overall quality does not decrease
    assert quality_after['overall_score'] >= quality_before['overall_score'], (
        f"Quality regression detected: "
        f"before={quality_before['overall_percent']:.2f}%, "
        f"after={quality_after['overall_percent']:.2f}% "
        f"(delta={quality_after['overall_percent'] - quality_before['overall_percent']:.2f}%)"
    )


def test_quality_regression_empty_strings_preserved():
    """Test that empty strings are handled consistently to avoid quality regression"""
    # Create a DataFrame with empty strings
    df = pd.DataFrame({
        'id': [1, 2, 3],
        'name': ['Alice', 'Bob', 'Charlie'],
        'email': ['alice@example.com', '', 'charlie@example.com'],
        'expected_close': ['2024-01-15', '2024-02-20', ''],
    })
    
    # No issues detected, just date standardization
    issues = []
    
    # Compute quality before
    quality_before = compute_quality_scores(df, {}, issues)
    
    # Apply fixes (should standardize dates)
    cleaned_df, summary, changes_df, removed_df = generate_naive_clean_with_summary(df, issues)
    
    # Compute quality after
    quality_after = compute_quality_scores(cleaned_df, {}, [])
    
    # Overall quality should not decrease
    assert quality_after['overall_score'] >= quality_before['overall_score'], (
        f"Quality regression with empty strings: "
        f"before={quality_before['overall_percent']:.2f}%, "
        f"after={quality_after['overall_percent']:.2f}%"
    )


def test_quality_no_regression_on_valid_data():
    """Test that quality score maintains or improves on valid data"""
    # Create a DataFrame with valid data
    df = pd.DataFrame({
        'id': [1, 2, 3, 4],
        'name': ['Alice', 'Bob', 'Charlie', 'Dave'],
        'email': ['alice@test.com', 'bob@test.com', 'charlie@test.com', 'dave@test.com'],
        'expected_close': ['2024-01-15', '2024-02-20', '2024-03-10', '2024-04-05'],
        'age': [30, 25, 35, 28],
    })
    
    issues = detect_issues(df)
    
    # Compute quality before
    quality_before = compute_quality_scores(df, {}, issues)
    
    # Apply fixes
    cleaned_df, summary, changes_df, removed_df = generate_naive_clean_with_summary(df, issues)
    
    # Compute quality after
    quality_after = compute_quality_scores(cleaned_df, {}, [])
    
    # Quality should not decrease
    assert quality_after['overall_score'] >= quality_before['overall_score'], (
        f"Quality regression on valid data: "
        f"before={quality_before['overall_percent']:.2f}%, "
        f"after={quality_after['overall_percent']:.2f}%"
    )

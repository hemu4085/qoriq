"""
Regression test for data quality score preservation.

This test ensures that applying fixes does not reduce the overall data quality score.
Specifically, it verifies that:
1. The fixer is conservative and doesn't introduce NaN for uncertain coercions
2. Quality scores are computed consistently before and after fixes
3. quality_after >= quality_before

Related to: Fix DQ score regression
"""
import subprocess
import json
import sys
from pathlib import Path


def test_quality_regression_with_diagnose_script():
    """
    Test that quality scores don't regress after applying fixes.
    
    Uses scripts/diagnose_quality.py with --json flag to verify that
    quality_after >= quality_before.
    """
    repo_root = Path(__file__).parent.parent
    script_path = repo_root / "scripts" / "diagnose_quality.py"
    before_path = repo_root / "tests" / "fixtures" / "before.csv"
    after_path = repo_root / "tests" / "fixtures" / "after.csv"
    
    # Run diagnose_quality.py with --json flag using same Python interpreter
    result = subprocess.run(
        [sys.executable, str(script_path), str(before_path), str(after_path), "--json"],
        capture_output=True,
        text=True,
        cwd=str(repo_root)
    )
    
    # Parse JSON output
    data = json.loads(result.stdout)
    
    # Verify structure
    assert "before" in data
    assert "after" in data
    assert "diagnosis" in data
    
    # Extract scores
    quality_before = data["before"]["overall_score"]
    quality_after = data["after"]["overall_score"]
    completeness_before = data["before"]["completeness"]
    completeness_after = data["after"]["completeness"]
    safety_before = data["before"]["safety"]
    safety_after = data["after"]["safety"]
    
    # Main assertion: quality should not regress
    assert quality_after >= quality_before, (
        f"Quality regressed: {quality_before:.4f} -> {quality_after:.4f} "
        f"(delta: {quality_after - quality_before:.4f})"
    )
    
    # Verify diagnosis flag
    assert data["diagnosis"]["quality_improved"] is True, (
        "Diagnosis reports quality did not improve"
    )
    
    # Log scores for visibility
    print("\nQuality Scores:")
    print(f"  Overall: {quality_before:.4f} -> {quality_after:.4f} (Δ {quality_after - quality_before:+.4f})")
    print(f"  Completeness: {completeness_before:.4f} -> {completeness_after:.4f} (Δ {completeness_after - completeness_before:+.4f})")
    print(f"  Safety: {safety_before:.4f} -> {safety_after:.4f} (Δ {safety_after - safety_before:+.4f})")


def test_fixer_preserves_unparseable_dates():
    """
    Test that the fixer preserves unparseable date values instead of converting to NaN.
    
    This ensures the conservative _safe_coerce_dates helper is working correctly.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    import pandas as pd
    from fixer import _safe_coerce_dates
    
    # Test data with mix of parseable and unparseable dates
    test_series = pd.Series([
        "2022-01-15",        # parseable
        "15/02/2021",        # parseable (dayfirst)
        "unclear_date",      # unparseable - should preserve
        "maybe_2022",        # unparseable - should preserve
        "",                  # empty - should become NaN
        "NA",                # null marker - should become NaN
        None,                # already None - should stay NaN
    ])
    
    result = _safe_coerce_dates(test_series)
    
    # Check parseable dates are standardized
    assert result[0] == "2022-01-15"
    assert result[1] == "2021-02-15"
    
    # Check unparseable dates are preserved (not converted to NaN)
    assert result[2] == "unclear_date"
    assert result[3] == "maybe_2022"
    
    # Check null markers are converted to NaN
    assert pd.isna(result[4])
    assert pd.isna(result[5])
    assert pd.isna(result[6])
    
    print("\nFixer test passed: unparseable dates preserved")
    print(f"  Input:  {test_series.tolist()}")
    print(f"  Output: {result.tolist()}")


def test_quality_normalizes_empty_strings():
    """
    Test that quality scoring normalizes empty strings to NaN for consistency.
    
    This ensures the _normalize_missing_values helper is working correctly.
    """
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    import pandas as pd
    from quality import _normalize_missing_values
    
    # Test data with empty strings and null markers
    test_df = pd.DataFrame({
        "col1": ["value", "", "NA", "N/A"],
        "col2": [1, 2, 3, 4],  # numeric column should not be affected
        "col3": ["a", "null", "None", "b"]
    })
    
    result = _normalize_missing_values(test_df)
    
    # Check empty strings and null markers are converted to NaN in object columns
    assert result["col1"][0] == "value"
    assert pd.isna(result["col1"][1])  # empty string -> NaN
    assert pd.isna(result["col1"][2])  # "NA" -> NaN
    assert pd.isna(result["col1"][3])  # "N/A" -> NaN
    
    # Check numeric columns are not affected
    assert result["col2"].tolist() == [1, 2, 3, 4]
    
    # Check other null markers
    assert result["col3"][0] == "a"
    assert pd.isna(result["col3"][1])  # "null" -> NaN
    assert pd.isna(result["col3"][2])  # "None" -> NaN
    assert result["col3"][3] == "b"
    
    print("\nQuality normalization test passed")
    print("  Empty strings and null markers converted to NaN")


if __name__ == "__main__":
    # Run tests
    test_quality_regression_with_diagnose_script()
    test_fixer_preserves_unparseable_dates()
    test_quality_normalizes_empty_strings()
    print("\n✓ All regression tests passed!")

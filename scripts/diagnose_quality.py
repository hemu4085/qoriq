#!/usr/bin/env python3
"""
Diagnostic script to reproduce quality score regression issue.
Loads a CSV, runs the fixer, compares quality scores before and after.
"""
import sys
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quality import compute_quality_scores
from src.fixer import generate_naive_clean_with_summary
from src.validator import detect_issues


def diagnose(csv_path: str):
    """Run diagnosis on a CSV file"""
    print(f"Loading {csv_path}...")
    # Use keep_default_na=False to preserve empty strings
    df = pd.read_csv(csv_path, keep_default_na=False, na_values=['NA', 'N/A', 'null', 'None'])
    
    print(f"\nOriginal DataFrame:")
    print(df)
    print(f"\nShape: {df.shape}")
    print(f"\nNull counts:")
    print(df.isna().sum())
    print(f"\nEmpty string counts:")
    for col in df.columns:
        empty_count = (df[col].astype(str) == '').sum()
        print(f"  {col}: {empty_count}")
    
    # Validate to get issues
    issues = detect_issues(df)
    print(f"\nValidation issues: {len(issues)}")
    
    # Compute quality before
    quality_before = compute_quality_scores(df, {}, issues)
    print(f"\n{'='*60}")
    print("QUALITY BEFORE FIXES:")
    print(f"{'='*60}")
    print(f"Overall: {quality_before['overall_percent']:.2f}%")
    for component, data in quality_before['components'].items():
        print(f"  {component:15s}: {data['score']*100:6.2f}%")
    
    # Apply fixes
    print(f"\n{'='*60}")
    print("APPLYING FIXES...")
    print(f"{'='*60}")
    cleaned_df, summary, changes_df, removed_df = generate_naive_clean_with_summary(df, issues)
    
    print(f"\nCleaned DataFrame:")
    print(cleaned_df)
    print(f"\nShape: {cleaned_df.shape}")
    print(f"\nNull counts after fixing:")
    print(cleaned_df.isna().sum())
    print(f"\nEmpty string counts after fixing:")
    for col in cleaned_df.columns:
        empty_count = (cleaned_df[col].astype(str) == '').sum()
        print(f"  {col}: {empty_count}")
    
    print(f"\nSummary:")
    print(f"  Rows changed: {summary['rows_changed_total']}")
    print(f"  Rows removed: {summary['rows_removed']}")
    print(f"  Columns changed: {summary['per_column_changed']}")
    
    # Compute quality after
    quality_after = compute_quality_scores(cleaned_df, {}, [])
    print(f"\n{'='*60}")
    print("QUALITY AFTER FIXES:")
    print(f"{'='*60}")
    print(f"Overall: {quality_after['overall_percent']:.2f}%")
    for component, data in quality_after['components'].items():
        print(f"  {component:15s}: {data['score']*100:6.2f}%")
    
    # Compare
    print(f"\n{'='*60}")
    print("COMPARISON (after - before):")
    print(f"{'='*60}")
    overall_delta = quality_after['overall_percent'] - quality_before['overall_percent']
    print(f"Overall: {overall_delta:+.2f}%")
    for component in quality_before['components']:
        before_score = quality_before['components'][component]['score']
        after_score = quality_after['components'][component]['score']
        delta = (after_score - before_score) * 100
        print(f"  {component:15s}: {delta:+6.2f}%")
    
    # Check regression
    if overall_delta < 0:
        print(f"\n❌ REGRESSION DETECTED: Quality decreased by {abs(overall_delta):.2f}%")
        return False
    else:
        print(f"\n✅ NO REGRESSION: Quality {'increased' if overall_delta > 0 else 'stayed the same'}")
        return True


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_quality.py <csv_file>")
        sys.exit(1)
    
    success = diagnose(sys.argv[1])
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Diagnose data quality for a CSV file before and after fixes.

Usage:
    python scripts/diagnose_quality.py before.csv after.csv
    
Computes and displays DQ scores for both files and shows the delta.
"""
import sys
import pandas as pd
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.quality import compute_quality_scores
from src.validator import detect_issues
from src.fixer import generate_naive_clean_with_summary


def diagnose_file(filepath: str, label: str) -> dict:
    """Load a CSV and compute its quality scores."""
    df = pd.read_csv(filepath)
    issues = detect_issues(df, missing_threshold=0.2)
    quality = compute_quality_scores(df)
    
    print(f"\n{'='*60}")
    print(f"{label}: {filepath}")
    print(f"{'='*60}")
    print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
    print(f"Issues detected: {len(issues)}")
    print("\nData Quality Scores:")
    print(f"  Overall:      {quality['overall_score']:.4f} ({quality['overall_percent']:.2f}%)")
    print(f"  Completeness: {quality['components']['completeness']['score']:.4f}")
    print(f"  Consistency:  {quality['components']['consistency']['score']:.4f}")
    print(f"  Semantic:     {quality['components']['semantic']['score']:.4f}")
    print(f"  Joinability:  {quality['components']['joinability']['score']:.4f}")
    print(f"  Safety:       {quality['components']['safety']['score']:.4f}")
    
    return quality


def compare_quality(before_quality: dict, after_quality: dict) -> None:
    """Compare and display quality deltas."""
    print(f"\n{'='*60}")
    print("Quality Change Analysis")
    print(f"{'='*60}")
    
    components = ['completeness', 'consistency', 'semantic', 'joinability', 'safety']
    
    overall_delta = after_quality['overall_score'] - before_quality['overall_score']
    print(f"Overall: {before_quality['overall_score']:.4f} → {after_quality['overall_score']:.4f} "
          f"(Δ {overall_delta:+.4f})")
    
    for comp in components:
        before = before_quality['components'][comp]['score']
        after = after_quality['components'][comp]['score']
        delta = after - before
        symbol = "✓" if delta >= 0 else "⚠"
        print(f"  {symbol} {comp.capitalize():12s}: {before:.4f} → {after:.4f} (Δ {delta:+.4f})")
    
    if overall_delta < 0:
        print(f"\n⚠️  QUALITY DEGRADATION DETECTED (Δ {overall_delta:.4f})")
        return False
    else:
        print(f"\n✓ Quality maintained or improved (Δ {overall_delta:+.4f})")
        return True


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/diagnose_quality.py <before.csv> [after.csv]")
        print("\nIf only one file is provided, applies fixes and compares before/after.")
        print("If two files are provided, compares them directly.")
        sys.exit(1)
    
    before_file = sys.argv[1]
    
    if len(sys.argv) >= 3:
        # Compare two existing files
        after_file = sys.argv[2]
        before_quality = diagnose_file(before_file, "BEFORE")
        after_quality = diagnose_file(after_file, "AFTER")
    else:
        # Apply fixes and compare
        before_quality = diagnose_file(before_file, "BEFORE FIXES")
        
        # Apply fixes
        df = pd.read_csv(before_file)
        issues = detect_issues(df, missing_threshold=0.2)
        cleaned_df, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(df, issues)
        
        # Compute after quality
        after_quality = compute_quality_scores(cleaned_df)
        
        print(f"\n{'='*60}")
        print("AFTER FIXES (in-memory)")
        print(f"{'='*60}")
        print(f"Rows: {len(cleaned_df)}, Columns: {len(cleaned_df.columns)}")
        print("\nData Quality Scores:")
        print(f"  Overall:      {after_quality['overall_score']:.4f} ({after_quality['overall_percent']:.2f}%)")
        print(f"  Completeness: {after_quality['components']['completeness']['score']:.4f}")
        print(f"  Consistency:  {after_quality['components']['consistency']['score']:.4f}")
        print(f"  Semantic:     {after_quality['components']['semantic']['score']:.4f}")
        print(f"  Joinability:  {after_quality['components']['joinability']['score']:.4f}")
        print(f"  Safety:       {after_quality['components']['safety']['score']:.4f}")
    
    # Compare
    success = compare_quality(before_quality, after_quality)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

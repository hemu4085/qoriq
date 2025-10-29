#!/usr/bin/env python3
"""
Diagnostic script to compute data quality scores before and after applying fixes.
Usage:
  python scripts/diagnose_quality.py <input.csv>
  python scripts/diagnose_quality.py <input.csv> --json
"""
import sys
import json
import argparse
from pathlib import Path

# Add parent directory to path to import src modules
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
from src.quality import compute_quality_scores
from src.validator import detect_issues
from src.fixer import generate_naive_clean_with_summary


def main():
    parser = argparse.ArgumentParser(description="Diagnose data quality before and after fixes")
    parser.add_argument("input_csv", help="Path to input CSV file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()
    
    # Load the input CSV
    try:
        df_before = pd.read_csv(args.input_csv)
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Compute quality before fixes
    quality_before = compute_quality_scores(df_before)
    
    # Validate to detect issues
    issues = detect_issues(df_before)
    
    # Apply fixes
    df_after, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(
        df_before, issues
    )
    
    # Compute quality after fixes
    quality_after = compute_quality_scores(df_after)
    
    # Prepare results
    results = {
        "before": {
            "overall_score": quality_before["overall_score"],
            "overall_percent": quality_before["overall_percent"],
            "components": {
                k: v["score"] for k, v in quality_before["components"].items()
            }
        },
        "after": {
            "overall_score": quality_after["overall_score"],
            "overall_percent": quality_after["overall_percent"],
            "components": {
                k: v["score"] for k, v in quality_after["components"].items()
            }
        },
        "diff": {
            "overall_score": quality_after["overall_score"] - quality_before["overall_score"],
            "overall_percent": quality_after["overall_percent"] - quality_before["overall_percent"],
            "components": {
                k: quality_after["components"][k]["score"] - quality_before["components"][k]["score"]
                for k in quality_before["components"].keys()
            }
        },
        "rows_before": len(df_before),
        "rows_after": len(df_after),
        "rows_removed": summary["rows_removed"],
        "rows_changed": summary["rows_changed_total"]
    }
    
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=" * 60)
        print("DATA QUALITY DIAGNOSIS")
        print("=" * 60)
        print(f"\nInput: {args.input_csv}")
        print(f"Rows: {results['rows_before']} -> {results['rows_after']} (removed: {results['rows_removed']})")
        print(f"Changed: {results['rows_changed']} rows")
        
        print("\n--- BEFORE FIXES ---")
        print(f"Overall: {results['before']['overall_percent']:.2f}%")
        for component, score in results['before']['components'].items():
            print(f"  {component:15s}: {score*100:6.2f}%")
        
        print("\n--- AFTER FIXES ---")
        print(f"Overall: {results['after']['overall_percent']:.2f}%")
        for component, score in results['after']['components'].items():
            print(f"  {component:15s}: {score*100:6.2f}%")
        
        print("\n--- DIFFERENCE (after - before) ---")
        print(f"Overall: {results['diff']['overall_percent']:+.2f}%")
        for component, diff in results['diff']['components'].items():
            print(f"  {component:15s}: {diff*100:+6.2f}%")
        
        if results['diff']['overall_score'] < 0:
            print("\n⚠️  WARNING: Quality decreased after fixes!")
        else:
            print("\n✓ Quality maintained or improved after fixes")
        print("=" * 60)
    
    return 0 if results['diff']['overall_score'] >= 0 else 1


if __name__ == "__main__":
    sys.exit(main())

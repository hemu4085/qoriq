#!/usr/bin/env python3
"""
Diagnose data quality scores before and after applying fixes.

Usage:
    python scripts/diagnose_quality.py before.csv after.csv [--json]

Computes quality scores for both datasets and reports whether quality improved.
With --json flag, outputs machine-readable JSON for test automation.
"""
import sys
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from quality import compute_quality_scores


def diagnose_quality(before_path: str, after_path: str, json_output: bool = False) -> dict:
    """
    Compare quality scores before and after fixes.
    
    Args:
        before_path: Path to CSV before fixes
        after_path: Path to CSV after fixes
        json_output: If True, return JSON-serializable dict
    
    Returns:
        Dictionary with before/after scores and diagnosis
    """
    # Load datasets
    df_before = pd.read_csv(before_path)
    df_after = pd.read_csv(after_path)
    
    # Compute quality scores
    quality_before = compute_quality_scores(df_before)
    quality_after = compute_quality_scores(df_after)
    
    # Extract key metrics
    result = {
        "before": {
            "overall_score": quality_before["overall_score"],
            "overall_percent": quality_before["overall_percent"],
            "completeness": quality_before["components"]["completeness"]["score"],
            "consistency": quality_before["components"]["consistency"]["score"],
            "semantic": quality_before["components"]["semantic"]["score"],
            "joinability": quality_before["components"]["joinability"]["score"],
            "safety": quality_before["components"]["safety"]["score"],
        },
        "after": {
            "overall_score": quality_after["overall_score"],
            "overall_percent": quality_after["overall_percent"],
            "completeness": quality_after["components"]["completeness"]["score"],
            "consistency": quality_after["components"]["consistency"]["score"],
            "semantic": quality_after["components"]["semantic"]["score"],
            "joinability": quality_after["components"]["joinability"]["score"],
            "safety": quality_after["components"]["safety"]["score"],
        },
        "diagnosis": {
            "quality_improved": quality_after["overall_score"] >= quality_before["overall_score"],
            "overall_delta": round(quality_after["overall_score"] - quality_before["overall_score"], 4),
            "completeness_delta": round(quality_after["components"]["completeness"]["score"] - quality_before["components"]["completeness"]["score"], 4),
            "safety_delta": round(quality_after["components"]["safety"]["score"] - quality_before["components"]["safety"]["score"], 4),
        }
    }
    
    return result


def main():
    parser = argparse.ArgumentParser(description="Diagnose data quality before and after fixes")
    parser.add_argument("before", help="Path to CSV before fixes")
    parser.add_argument("after", help="Path to CSV after fixes")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    
    args = parser.parse_args()
    
    result = diagnose_quality(args.before, args.after, args.json)
    
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("=" * 60)
        print("Data Quality Diagnosis")
        print("=" * 60)
        print("\nBEFORE FIXES:")
        print(f"  Overall Score: {result['before']['overall_score']:.4f} ({result['before']['overall_percent']:.2f}%)")
        print(f"  Completeness:  {result['before']['completeness']:.4f}")
        print(f"  Consistency:   {result['before']['consistency']:.4f}")
        print(f"  Semantic:      {result['before']['semantic']:.4f}")
        print(f"  Joinability:   {result['before']['joinability']:.4f}")
        print(f"  Safety:        {result['before']['safety']:.4f}")
        
        print("\nAFTER FIXES:")
        print(f"  Overall Score: {result['after']['overall_score']:.4f} ({result['after']['overall_percent']:.2f}%)")
        print(f"  Completeness:  {result['after']['completeness']:.4f}")
        print(f"  Consistency:   {result['after']['consistency']:.4f}")
        print(f"  Semantic:      {result['after']['semantic']:.4f}")
        print(f"  Joinability:   {result['after']['joinability']:.4f}")
        print(f"  Safety:        {result['after']['safety']:.4f}")
        
        print("\nDIAGNOSIS:")
        print(f"  Quality Improved:   {'✓ YES' if result['diagnosis']['quality_improved'] else '✗ NO'}")
        print(f"  Overall Delta:      {result['diagnosis']['overall_delta']:+.4f}")
        print(f"  Completeness Delta: {result['diagnosis']['completeness_delta']:+.4f}")
        print(f"  Safety Delta:       {result['diagnosis']['safety_delta']:+.4f}")
        print("=" * 60)
        
        if not result['diagnosis']['quality_improved']:
            sys.exit(1)


if __name__ == "__main__":
    main()

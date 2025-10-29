#!/usr/bin/env python
"""
Diagnose quality scores before and after applying fixes.

Usage:
    python scripts/diagnose_quality.py <before.csv> <after.csv> [--json]

Compares quality scores between the "before" CSV and "after" CSV (post-fix).
With --json, outputs a JSON summary to stdout.
"""
import sys
import json
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import pandas as pd
from quality import compute_quality_scores


def main():
    parser = argparse.ArgumentParser(description="Diagnose quality scores before and after fixes")
    parser.add_argument("before_csv", help="Path to before.csv")
    parser.add_argument("after_csv", help="Path to after.csv")
    parser.add_argument("--json", action="store_true", help="Output JSON summary to stdout")
    args = parser.parse_args()

    # Load data
    df_before = pd.read_csv(args.before_csv)
    df_after = pd.read_csv(args.after_csv)

    # Compute quality scores
    quality_before = compute_quality_scores(df_before)
    quality_after = compute_quality_scores(df_after)

    if args.json:
        # Output JSON summary
        summary = {
            "quality_before": quality_before["overall_score"],
            "quality_after": quality_after["overall_score"],
            "completeness_before": quality_before["components"]["completeness"]["score"],
            "completeness_after": quality_after["components"]["completeness"]["score"],
            "safety_before": quality_before["components"]["safety"]["score"],
            "safety_after": quality_after["components"]["safety"]["score"],
            "consistency_before": quality_before["components"]["consistency"]["score"],
            "consistency_after": quality_after["components"]["consistency"]["score"],
            "semantic_before": quality_before["components"]["semantic"]["score"],
            "semantic_after": quality_after["components"]["semantic"]["score"],
            "joinability_before": quality_before["components"]["joinability"]["score"],
            "joinability_after": quality_after["components"]["joinability"]["score"],
        }
        print(json.dumps(summary, indent=2))
    else:
        # Human-readable output
        print("Quality Score Comparison")
        print("=" * 60)
        print(f"\nBefore: {quality_before['overall_score']:.4f} ({quality_before['overall_percent']:.2f}%)")
        print(f"After:  {quality_after['overall_score']:.4f} ({quality_after['overall_percent']:.2f}%)")
        print(f"\nChange: {quality_after['overall_score'] - quality_before['overall_score']:.4f}")
        
        print("\n\nComponent Breakdown:")
        print("-" * 60)
        for component in ["completeness", "consistency", "semantic", "joinability", "safety"]:
            before_score = quality_before["components"][component]["score"]
            after_score = quality_after["components"][component]["score"]
            change = after_score - before_score
            print(f"{component.capitalize():15s}: {before_score:.4f} -> {after_score:.4f} ({change:+.4f})")


if __name__ == "__main__":
    main()

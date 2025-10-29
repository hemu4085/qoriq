#!/usr/bin/env python3
"""
Diagnose data quality for a CSV file.

Reads a CSV, computes quality scores, and optionally outputs JSON for machine parsing.
Useful for testing and regression analysis.

Usage:
    python scripts/diagnose_quality.py <path_to_csv> [--json]
"""
import sys
import json
import argparse
import pandas as pd
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from quality import compute_quality_scores


def main():
    parser = argparse.ArgumentParser(description="Diagnose data quality for a CSV file")
    parser.add_argument("csv_path", help="Path to CSV file")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    args = parser.parse_args()

    # Load CSV
    try:
        df = pd.read_csv(args.csv_path)
    except Exception as e:
        print(f"Error reading CSV: {e}", file=sys.stderr)
        sys.exit(1)

    # Compute quality scores
    quality_result = compute_quality_scores(df)

    if args.json:
        # Output JSON for machine parsing
        print(json.dumps(quality_result, indent=2))
    else:
        # Human-readable output
        print(f"Data Quality Analysis for: {args.csv_path}")
        print(f"Rows: {len(df)}, Columns: {len(df.columns)}")
        print(f"\nOverall Score: {quality_result['overall_score']} ({quality_result['overall_percent']}%)")
        print("\nComponent Scores:")
        for component, data in quality_result['components'].items():
            print(f"  {component.capitalize():15s}: {data['score']:.4f}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

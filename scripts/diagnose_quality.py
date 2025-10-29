#!/usr/bin/env python3
"""
Compare data quality before/after fixes and optionally emit machine-readable JSON.

Usage:
    python scripts/diagnose_quality.py before.csv after.csv [--json]

This script uses src/quality.score_dataframe for the metric computations. It
is intentionally lightweight and adds a --json flag so tests can parse its output.
"""
import argparse
import json
import sys
import pandas as pd
import os

# Try to import the project's scoring function; fall back to a minimal local
# implementation if the import fails (keeps the script robust).
try:
    from src.quality import score_dataframe  # type: ignore
except Exception:
    # Minimal fallback (should be identical to src/quality.score_dataframe above)
    def score_dataframe(df: pd.DataFrame):
        # Basic completeness and safety heuristics
        df_norm = df.replace("", pd.NA)
        total_cells = df_norm.size
        non_missing = df_norm.notna().sum().sum()
        completeness = 100.0 * (non_missing / total_cells) if total_cells > 0 else 100.0
        unsafe_mask = df_norm.astype(str).apply(lambda col: col.str.strip().str.lower() == "not-a-date")
        unsafe_count = unsafe_mask.sum().sum()
        safe_count = total_cells - unsafe_count
        safety = 100.0 * (safe_count / total_cells) if total_cells > 0 else 100.0
        quality = (completeness + safety) / 2.0
        return {
            "completeness": float(round(completeness, 3)),
            "safety": float(round(safety, 3)),
            "quality": float(round(quality, 3)),
        }

def _read_csv(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    return pd.read_csv(path)

def main():
    parser = argparse.ArgumentParser(description="Compare data quality before/after fixes")
    parser.add_argument("before_csv", help="Path to original CSV")
    parser.add_argument("after_csv", help="Path to fixed CSV")
    parser.add_argument("--json", action="store_true", help="Emit JSON summary to stdout")
    args = parser.parse_args()

    try:
        df_before = _read_csv(args.before_csv)
        df_after = _read_csv(args.after_csv)
    except Exception as exc:
        print(f"Error reading CSVs: {exc}", file=sys.stderr)
        sys.exit(2)

    before_metrics = score_dataframe(df_before)
    after_metrics = score_dataframe(df_after)

    summary = {
        "quality_before": before_metrics["quality"],
        "quality_after": after_metrics["quality"],
        "completeness_before": before_metrics["completeness"],
        "completeness_after": after_metrics["completeness"],
        "safety_before": before_metrics["safety"],
        "safety_after": after_metrics["safety"],
    }

    if args.json:
        print(json.dumps(summary))
    else:
        print("=== Data Quality Diagnostic ===")
        print(f"Quality before: {summary['quality_before']}")
        print(f"Quality after : {summary['quality_after']}")
        print(f"Completeness before: {summary['completeness_before']}")
        print(f"Completeness after : {summary['completeness_after']}")
        print(f"Safety before: {summary['safety_before']}")
        print(f"Safety after : {summary['safety_after']}")

if __name__ == "__main__":
    main()
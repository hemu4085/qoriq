# Minimal normalization helper and a small scorer used by the diagnostic script.
# The real project scoring implementation may be more complex; this keeps scoring
# deterministic for the regression test and normalizes empty strings to np.nan
# so completeness/safety counts are consistent.
import pandas as pd
import numpy as np
from typing import Dict

def _normalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert empty strings to np.nan so scoring counts missing values consistently.
    Only pure empty strings are converted; other values are preserved.
    """
    return df.replace("", np.nan)

def score_dataframe(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute simple quality metrics for diagnostics:
      - completeness: percent of non-missing cells (after normalizing "")
      - safety: percent of cells that pass a simple 'safety' check
      - quality: average of completeness and safety (0..100 scale)
    This function returns values on 0..100 scale (floats).
    """
    if df is None or df.empty:
        return {
            "completeness": 100.0,
            "safety": 100.0,
            "quality": 100.0,
        }

    df_norm = _normalize_missing_values(df.copy())

    # completeness: fraction of non-missing cells
    total_cells = df_norm.size
    non_missing = df_norm.notna().sum().sum()
    completeness = 100.0 * (non_missing / total_cells) if total_cells > 0 else 100.0

    # safety: simple heuristic -> fraction of cells that are not exactly the string "not-a-date"
    # Use vectorized string operations column-wise to avoid the deprecated DataFrame.applymap.
    # Convert values to strings and compare using pandas string methods for speed and correctness.
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
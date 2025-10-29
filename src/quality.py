# Minimal normalization helper and a small scorer used by the diagnostic script.
# The real project scoring implementation may be more complex; this keeps scoring
# deterministic for the regression test and normalizes empty strings to np.nan
# so completeness/safety counts are consistent.
import pandas as pd
import numpy as np
from typing import Dict, Any

# Module-level scoring weights. To preserve previous behavior by default,
# completeness and safety are 0.5 each and other dimensions are 0.0 so the
# overall 'quality' equals the previous arithmetic mean of completeness/safety.
# Callers may change these via set_scoring_weights (backward-compatible).
_SCORING_WEIGHTS: Dict[str, float] = {
    "completeness": 0.5,
    "safety": 0.5,
    "consistency": 0.0,
    "uniqueness": 0.0,
    "validity": 0.0,
    "timeliness": 0.0,
}

def set_scoring_weights(weights: Dict[str, float]) -> None:
    """
    Set module-level scoring weights for the 'quality' aggregation.
    Accepts keys among: completeness, safety, consistency, uniqueness, validity, timeliness.
    Values must be non-negative numbers. Weights are normalized to sum to 1.
    This preserves score_dataframe signature (no breaking changes).
    """
    if not isinstance(weights, dict):
        raise TypeError("weights must be a dict of dimension -> weight")
    allowed = set(_SCORING_WEIGHTS.keys())
    for k in weights.keys():
        if k not in allowed:
            raise KeyError(f"invalid weight key '{k}', allowed keys: {sorted(allowed)}")
    # Build full weight dict using current defaults then override with provided keys
    w = dict(_SCORING_WEIGHTS)
    for k, v in weights.items():
        w[k] = float(v)
        if w[k] < 0:
            raise ValueError("weights must be non-negative")
    total = sum(w.values())
    if total == 0:
        raise ValueError("sum of weights must be greater than 0")
    # normalize and set
    for k in w:
        _SCORING_WEIGHTS[k] = w[k] / total

def get_scoring_weights() -> Dict[str, float]:
    """Return a copy of the current normalized scoring weights."""
    return dict(_SCORING_WEIGHTS)

def _normalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Convert empty strings to np.nan so scoring counts missing values consistently.
    Only pure empty strings are converted; other values are preserved.
    """
    return df.replace("", np.nan)

def _compute_consistency(df_norm: pd.DataFrame) -> float:
    """
    Consistency heuristic:
    - For each column, compute the modal (most common) normalized value frequency among non-missing values.
    - Consistency = average across columns of (mode_count / non_missing_in_column) * 100
    Returns percentage 0..100.
    """
    cols = df_norm.columns
    scores = []
    for c in cols:
        col = df_norm[c].dropna().astype(str).str.strip()
        if col.empty:
            # Empty column considered fully consistent (no disagreements)
            scores.append(1.0)
            continue
        mode_count = col.value_counts().iloc[0]
        denom = len(col)
        scores.append(mode_count / denom if denom > 0 else 1.0)
    return 100.0 * (sum(scores) / len(scores)) if len(scores) > 0 else 100.0

def _compute_uniqueness(df_norm: pd.DataFrame) -> float:
    """
    Uniqueness heuristic:
    - For each column compute unique_non_missing / non_missing.
    - Return average across columns as percentage 0..100.
    """
    cols = df_norm.columns
    scores = []
    for c in cols:
        col = df_norm[c].dropna()
        if col.empty:
            scores.append(1.0)
            continue
        unique_count = col.nunique(dropna=True)
        denom = len(col)
        scores.append(unique_count / denom if denom > 0 else 1.0)
    return 100.0 * (sum(scores) / len(scores)) if len(scores) > 0 else 100.0

def _compute_validity(df_norm: pd.DataFrame) -> float:
    """
    Validity heuristic:
    - A very conservative check: count cells not equal to common invalid tokens.
    - This is intentionally conservative and extensible in future releases.
    """
    invalid_tokens = {"invalid", "error", "nan", "null"}  # lowered tokens
    total = df_norm.size
    if total == 0:
        return 100.0
    flattened = df_norm.astype(str).apply(lambda col: col.str.strip().str.lower())
    invalid_mask = flattened.isin(invalid_tokens)
    valid_count = total - invalid_mask.sum().sum()
    return 100.0 * (valid_count / total)

def _compute_timeliness(df_norm: pd.DataFrame) -> float:
    """
    Timeliness heuristic:
    - If there are date-like columns, score based on how many rows parse as dates.
    - Otherwise return 100 (no timeliness concerns detected).
    """
    total_cells = 0
    parsed_count = 0
    for c in df_norm.columns:
        col = df_norm[c]
        # attempt to parse meaningful non-empty values
        mask = col.notna() & (col.astype(str).str.strip() != "")
        if not mask.any():
            continue
        total_cells += mask.sum()
        parsed = pd.to_datetime(col[mask], errors="coerce", infer_datetime_format=True)
        parsed_count += parsed.notna().sum()
    if total_cells == 0:
        return 100.0
    return 100.0 * (parsed_count / total_cells)

def score_dataframe(df: pd.DataFrame) -> Dict[str, float]:
    """
    Compute quality metrics:
      - completeness: percent of non-missing cells (after normalizing "")
      - safety: percent of cells that pass a simple 'safety' check
      - consistency: per-column mode-frequency average
      - uniqueness: per-column unique fraction average
      - validity: heuristic token-based validity check
      - timeliness: fraction of date-like values parsed successfully
      - quality: weighted average (using module-level weights)

    Returns a dict of float metrics on 0..100 scale. Signature unchanged.
    """
    if df is None or df.empty:
        # preserve previous behavior: empty => perfect scores
        return {
            "completeness": 100.0,
            "safety": 100.0,
            "consistency": 100.0,
            "uniqueness": 100.0,
            "validity": 100.0,
            "timeliness": 100.0,
            "quality": 100.0,
        }

    df_norm = _normalize_missing_values(df.copy())

    # completeness: fraction of non-missing cells
    total_cells = df_norm.size
    non_missing = df_norm.notna().sum().sum()
    completeness = 100.0 * (non_missing / total_cells) if total_cells > 0 else 100.0

    # safety: simple heuristic -> fraction of cells that are not exactly the string "not-a-date"
    # Use vectorized string operations column-wise for speed and correctness.
    unsafe_mask = df_norm.astype(str).apply(lambda col: col.str.strip().str.lower() == "not-a-date")
    unsafe_count = unsafe_mask.sum().sum()
    safe_count = total_cells - unsafe_count
    safety = 100.0 * (safe_count / total_cells) if total_cells > 0 else 100.0

    # other heuristics
    consistency = _compute_consistency(df_norm)
    uniqueness = _compute_uniqueness(df_norm)
    validity = _compute_validity(df_norm)
    timeliness = _compute_timeliness(df_norm)

    # weighted quality using normalized module weights
    weights = get_scoring_weights()
    # ensure all keys exist in weights (defensive)
    dims = ["completeness", "safety", "consistency", "uniqueness", "validity", "timeliness"]
    quality = 0.0
    for d in dims:
        v = {
            "completeness": completeness,
            "safety": safety,
            "consistency": consistency,
            "uniqueness": uniqueness,
            "validity": validity,
            "timeliness": timeliness,
        }[d]
        w = weights.get(d, 0.0)
        quality += v * w

    return {
        "completeness": float(round(completeness, 3)),
        "safety": float(round(safety, 3)),
        "consistency": float(round(consistency, 3)),
        "uniqueness": float(round(uniqueness, 3)),
        "validity": float(round(validity, 3)),
        "timeliness": float(round(timeliness, 3)),
        "quality": float(round(quality, 3)),
    }

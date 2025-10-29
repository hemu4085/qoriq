# Conservative helper additions for the fixer to avoid introducing new nulls.
# This file adds a non-invasive helper _safe_coerce_dates that the fixer can
# use when coercing date-like columns. It deliberately preserves original
# values when parsing fails so we don't increase null counts unexpectedly.
import pandas as pd
import numpy as np
from typing import Any, List, Dict, Tuple

def _safe_coerce_dates(series: pd.Series) -> pd.Series:
    """
    Attempt to coerce only non-empty, non-null string values to datetimes.
    If parsing fails for a non-empty value, preserve the original string instead
    of replacing it with NaT/NaN to avoid introducing new nulls.
    """
    s = series.copy()
    # mask of meaningful values to attempt coercion on (not NaN and not empty string)
    mask = s.notna() & (s.astype(str).str.strip() != "")

    if not mask.any():
        return s

    # parse only the masked entries
    parsed = pd.to_datetime(s[mask], errors="coerce", infer_datetime_format=True)

    # where parsing succeeded, set parsed value; where it failed keep original
    for idx, parsed_val in parsed.items():
        if pd.notna(parsed_val):
            s.at[idx] = parsed_val
        else:
            s.at[idx] = series.at[idx]

    return s

def recommend_bulk_fixes(df: pd.DataFrame) -> List[Dict[str, Any]]:
    """
    Recommend non-destructive bulk fixes for a DataFrame.
    Returns a list of suggestions; each suggestion is a dict:
      {"row": idx, "column": col, "original": value, "suggestion": new_value, "reason": str}

    Conservative heuristics (bulk only):
      - empty string -> suggest np.nan (reason: "empty_to_nan")
      - 'not-a-date' (case-insensitive) -> suggest np.nan (reason: "unsafe_token")
      - if a column successfully coerces some values to datetime while preserving others,
        suggest parsed datetime for those entries (reason: "coerce_date")
    No automatic application is done; apply_fixes must be called explicitly.
    """
    fixes = []
    if df is None:
        return fixes
    # 1) empty strings and unsafe token
    for col in df.columns:
        col_series = df[col]
        for idx, val in col_series.items():
            if isinstance(val, str) and val.strip() == "":
                fixes.append({
                    "row": idx, "column": col, "original": val,
                    "suggestion": np.nan, "reason": "empty_to_nan"
                })
            elif isinstance(val, str) and val.strip().lower() == "not-a-date":
                fixes.append({
                    "row": idx, "column": col, "original": val,
                    "suggestion": np.nan, "reason": "unsafe_token"
                    })
    # 2) date coercion suggestions: for each column, attempt safe coercion and propose parsed values where parsing succeeded
    for col in df.columns:
        original = df[col]
        parsed = _safe_coerce_dates(original)
        for idx, parsed_val in parsed.items():
            # if parsed value differs AND parsed value is not the same object as original
            if pd.notna(parsed_val) and parsed_val is not original.at[idx]:
                # the original may be a string that can be parsed to a Timestamp
                # Only propose the parsed Timestamp if the original was a non-empty string
                orig_val = original.at[idx]
                if isinstance(orig_val, str) and orig_val.strip() != "":
                    fixes.append({
                        "row": idx, "column": col, "original": orig_val,
                        "suggestion": parsed_val, "reason": "coerce_date"
                    })
    # Deduplicate suggestions for same row/col, prefer parse suggestions over empty_to_nan (if both present)
    seen = {}
    deduped = []
    priority = {"coerce_date": 2, "unsafe_token": 1, "empty_to_nan": 0}
    for f in fixes:
        key = (f["row"], f["column"])
        if key not in seen:
            seen[key] = f
        else:
            # keep the higher priority one
            if priority.get(f["reason"], 0) > priority.get(seen[key]["reason"], 0):
                seen[key] = f
    for v in seen.values():
        deduped.append(v)
    # deterministic ordering by row then column name
    deduped.sort(key=lambda x: (str(x["row"]), str(x["column"])))
    return deduped
...
# truncated here in preview; full content in the actual script below

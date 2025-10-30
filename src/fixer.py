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

    # parse only the masked entries (removed deprecated infer_datetime_format kwarg)
    parsed = pd.to_datetime(s[mask], errors="coerce")

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

def apply_fixes(df: pd.DataFrame, recs: List[Dict[str, Any]]) -> Tuple[pd.DataFrame, List[Dict[str, Any]]]:
    """
    Apply a list of recommendations (as produced by recommend_bulk_fixes) to a copy
    of the DataFrame and return (fixed_df, applied_list).

    applied_list contains one dict per recommendation, copied from the input recommendation
    and augmented with at least the key "applied": bool. If applying failed or skipped,
    an "error" or "reason_applied" field may be present.
    """
    if df is None:
        return df, []

    out = df.copy(deep=True)
    applied = []

    if not recs:
        return out, applied

    for rec in recs:
        r = dict(rec)  # shallow copy so we can augment
        r.setdefault("applied", False)

        row = r.get("row")
        col = r.get("column")
        suggestion = r.get("suggestion")

        # Validate column
        if col not in out.columns:
            r["error"] = "missing_column"
            applied.append(r)
            continue

        # Validate row exists
        if row not in out.index:
            r["error"] = "missing_row"
            applied.append(r)
            continue

        # Current value
        try:
            current = out.at[row, col]
        except Exception as e:
            r["error"] = f"access_error: {e}"
            applied.append(r)
            continue

        # Compare current vs suggestion, treating NaNs as equal
        same = False
        try:
            if pd.isna(current) and pd.isna(suggestion):
                same = True
            else:
                # Use pandas-aware comparison where possible
                same = current == suggestion
        except Exception:
            same = False

        if same:
            r["applied"] = False
            r["reason_applied"] = "no_change"
            applied.append(r)
            continue

        # Attempt to apply
        try:
            out.at[row, col] = suggestion
            r["applied"] = True
            applied.append(r)
        except Exception as e:
            r["error"] = str(e)
            r["applied"] = False
            applied.append(r)

    return out, applied
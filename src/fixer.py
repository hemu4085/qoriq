"""
Naive bulk fixer for Qoriq v1.x with robust date standardization.

- Standardizes 'expected_close' if present.
- Heuristically finds other date-like columns (columns containing 'date', 'time',
  'timestamp' or partially parseable) and standardizes them.
- Uses pandas.to_datetime with a dayfirst fallback for ambiguous formats.
- Applies other naive fixes (missing imputation, invalid-email masking, dtype coercion)
  based on issues detected (and always standardizes expected_close).
Returns:
  cleaned_df, summary, changes_df, removed_rows_df
"""
from typing import Dict, Any, List, Tuple, Optional
import re
import pandas as pd

EMAIL_RE = re.compile(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$')

def _is_valid_email(s: Optional[str]) -> bool:
    if s is None:
        return False
    try:
        return bool(EMAIL_RE.match(str(s)))
    except Exception:
        return False

def _coerce_numeric_if_mostly(ser: pd.Series, threshold: float = 0.8) -> pd.Series:
    coerced = pd.to_numeric(ser, errors="coerce")
    if coerced.notna().sum() / max(1, len(ser)) >= threshold:
        return coerced
    return ser

def _standardize_dates_series(ser: pd.Series) -> pd.Series:
    """
    Parse a Series of date-like strings and return ISO date strings YYYY-MM-DD.
    For unparseable dates, preserve the original value to avoid introducing NaN.
    
    Strategy:
      - Use pd.to_datetime(..., dayfirst=False) for initial parse
      - For unparsed entries, retry with dayfirst=True
      - For still-unparsed entries, keep the original value (don't convert to NaN)
      - This prevents quality score degradation from introducing new missing values
    """
    if ser is None or ser.shape[0] == 0:
        return ser
    
    # Store original values to preserve them for unparseable dates
    original = ser.copy()
    
    # Only normalize truly null markers to None (not empty strings from valid data)
    raw = ser.replace({"NA": None, "N/A": None, "null": None, "None": None})
    
    # attempt parse (dayfirst False)
    parsed = pd.to_datetime(raw.astype(str), errors="coerce", dayfirst=False)
    
    # retry with dayfirst True for those not parsed
    mask_not_parsed = parsed.isna() & raw.notna()
    if mask_not_parsed.any():
        parsed_alt = pd.to_datetime(raw[mask_not_parsed].astype(str), errors="coerce", dayfirst=True)
        parsed.loc[mask_not_parsed] = parsed_alt
    
    # Convert successfully parsed dates to YYYY-MM-DD format
    result = parsed.dt.strftime("%Y-%m-%d").where(parsed.notna(), original)
    
    # For entries that were originally NaN, keep them as NaN (not as string "nan")
    result = result.where(raw.notna(), None)
    
    return result

def _guess_date_like_columns(df: pd.DataFrame, issues: List[Dict[str, Any]]) -> List[str]:
    """
    Heuristic: include columns that
      - contain the substrings 'date', 'time', 'timestamp', 'close', or 'expected_close'
      - OR were detected as date_partial_parse by the validator in issues
      - OR have at least 5% parseable values (quick sniff)
    """
    date_cols = set()
    for c in df.columns:
        lc = c.lower()
        if any(k in lc for k in ("date", "time", "timestamp", "close", "expected_close")):
            date_cols.add(c)

    # include columns flagged by validator
    for it in issues:
        if it.get("type") == "date_partial_parse":
            for c in (it.get("columns") or []):
                if c in df.columns:
                    date_cols.add(c)

    # sniff columns that are mostly parseable
    for c in df.columns:
        if c in date_cols:
            continue
        ser = df[c].dropna().astype(str).head(1000)  # sample up to 1000 values
        if ser.empty:
            continue
        parsed = pd.to_datetime(ser, errors="coerce", dayfirst=False)
        parse_frac = parsed.notna().sum() / len(ser)
        if parse_frac >= 0.05:  # at least 5% parseable
            date_cols.add(c)
    return list(date_cols)

def generate_naive_clean_with_summary(df: pd.DataFrame,
                                      issues: List[Dict[str, Any]],
                                      max_preview_rows: int = 200
                                      ) -> Tuple[pd.DataFrame, Dict[str, Any], pd.DataFrame, pd.DataFrame]:
    """
    Apply bulk naive fixes for detected issues and date standardization.
    Returns:
      - cleaned_df
      - summary: per_column_changed, rows_removed, rows_changed_total, preview_changed_rows_returned, preview_changed_limit
      - changes_df: preview of changed rows with before/after values (up to max_preview_rows)
      - removed_rows_df: rows removed due to dedupe (full set)
    """
    if df is None or df.shape[0] == 0:
        return df.copy() if df is not None else pd.DataFrame(), {"per_column_changed": {}, "rows_removed": 0, "rows_changed_total": 0, "preview_changed_rows_returned": 0, "preview_changed_limit": max_preview_rows}, pd.DataFrame(), pd.DataFrame()

    orig = df.copy().reset_index(drop=True)
    pre_dedupe = orig.copy()

    # Build transform sets from issues
    cols_missing_high = set()
    cols_invalid_email = set()
    cols_dtype_mismatch = set()
    duplicate_col_sets: List[Tuple[str, ...]] = []

    for it in issues:
        typ = it.get("type")
        cols = it.get("columns", []) or []
        if typ == "missing_high":
            cols_missing_high.update(cols)
        elif typ == "invalid_email":
            cols_invalid_email.update(cols)
        elif typ == "dtype_mismatch":
            cols_dtype_mismatch.update(cols)
        elif typ == "duplicate_rows":
            if cols:
                duplicate_col_sets.append(tuple(cols))

    # Date columns: guess heuristically + always include expected_close if present
    cols_date_like = set(_guess_date_like_columns(orig, issues))
    if "expected_close" in orig.columns:
        cols_date_like.add("expected_close")

    # Apply missing-high transforms
    for c in list(cols_missing_high):
        if c not in pre_dedupe.columns:
            continue
        if pd.api.types.is_numeric_dtype(pre_dedupe[c]):
            med = pd.to_numeric(pre_dedupe[c], errors="coerce").median(skipna=True)
            if not pd.isna(med):
                pre_dedupe[c] = pre_dedupe[c].fillna(med)
        else:
            pre_dedupe[c] = pre_dedupe[c].fillna("")

    # Apply invalid-email masking
    for c in list(cols_invalid_email):
        if c not in pre_dedupe.columns:
            continue
        ser = pre_dedupe[c].astype(str)
        mask_has_at = ser.str.contains("@", na=False)
        mask_invalid = mask_has_at & ~ser.apply(_is_valid_email)
        pre_dedupe.loc[mask_invalid, c] = ""

    # Apply dtype coercion
    for c in list(cols_dtype_mismatch):
        if c not in pre_dedupe.columns:
            continue
        pre_dedupe[c] = _coerce_numeric_if_mostly(pre_dedupe[c])

    # Apply date standardization for detected/guessed date-like columns
    for c in list(cols_date_like):
        if c not in pre_dedupe.columns:
            continue
        try:
            pre_dedupe[c] = _standardize_dates_series(pre_dedupe[c])
        except Exception:
            # on parsing error, leave column unchanged
            pass

    # Compute per-column changed counts across the full dataset
    per_column_changed: Dict[str, int] = {}
    for c in orig.columns:
        before = orig[c].fillna("__QORIQ_NAN__").astype(str)
        after = pre_dedupe[c].fillna("__QORIQ_NAN__").astype(str)
        per_column_changed[c] = int((~before.eq(after)).sum())

    # Detect and remove duplicates (union of duplicate columns)
    removed_rows_df = orig.iloc[0:0].copy()
    if duplicate_col_sets:
        union_cols = list({col for cols in duplicate_col_sets for col in cols})
        if union_cols:
            dup_mask = orig.duplicated(subset=union_cols, keep='first')
            removed_rows_df = orig.loc[dup_mask].copy()
            cleaned_df = pre_dedupe.drop_duplicates(subset=union_cols, keep='first').reset_index(drop=True)
        else:
            cleaned_df = pre_dedupe.reset_index(drop=True)
    else:
        cleaned_df = pre_dedupe.reset_index(drop=True)

    # Compute rows changed total (value transforms) plus removed rows
    any_changed_mask = pd.Series(False, index=orig.index)
    for c in orig.columns:
        before = orig[c].fillna("__QORIQ_NAN__").astype(str)
        after_values = pre_dedupe[c].fillna("__QORIQ_NAN__").astype(str)
        any_changed_mask = any_changed_mask | (~before.eq(after_values))
    changed_row_indices = list(any_changed_mask[any_changed_mask].index)
    rows_changed_total = len(changed_row_indices) + (0 if removed_rows_df is None else len(removed_rows_df))

    # Build preview changes_df showing before/after columns for up to max_preview_rows changed rows
    preview_indices = changed_row_indices[:max_preview_rows]
    changes_preview_rows = []
    for idx in preview_indices:
        rec = {"_orig_index": int(idx)}
        row_before = orig.loc[idx]
        row_after = pre_dedupe.loc[idx]
        for c in orig.columns:
            bval = row_before[c]
            aval = row_after[c]
            if (pd.isna(bval) and pd.isna(aval)) or (str(bval) == str(aval)):
                continue
            rec[f"{c}__before"] = None if pd.isna(bval) else bval
            rec[f"{c}__after"] = None if pd.isna(aval) else aval
        if len(rec) > 1:
            changes_preview_rows.append(rec)
    changes_df = pd.DataFrame(changes_preview_rows)

    summary = {
        "per_column_changed": {k: int(v) for k, v in per_column_changed.items() if v > 0},
        "rows_removed": int(len(removed_rows_df)) if removed_rows_df is not None else 0,
        "rows_changed_total": int(rows_changed_total),
        "preview_changed_rows_returned": int(len(changes_df)),
        "preview_changed_limit": int(max_preview_rows),
        "date_columns_standardized": list(cols_date_like)
    }

    return cleaned_df, summary, changes_df, removed_rows_df
"""
Data quality scoring module for Qoriq.

Computes heuristic scores (0..1) for:
- completeness
- consistency
- semantic
- joinability
- safety

Returns an explainable dict with per-component scores and details.
"""
from typing import Dict, Any, List
import re
import pandas as pd
import numpy as np

_email_re = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
_phone_re = re.compile(r"\+?\d[\d\-\s]{6,}\d")
_ssn_re = re.compile(r"^\d{3}-\d{2}-\d{4}$")

def _normalize_missing_values(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize missing values by replacing empty strings with np.nan.
    This ensures consistent handling of missing values across all scoring functions.
    
    Args:
        df: Input dataframe
        
    Returns:
        A copy of the dataframe with empty strings replaced by np.nan
    """
    df_normalized = df.copy()
    for col in df_normalized.columns:
        if df_normalized[col].dtype == object:
            # Replace empty strings with NaN for consistent missing value handling
            df_normalized[col] = df_normalized[col].replace({"": np.nan, " ": np.nan})
    return df_normalized

def _col_completeness(df: pd.DataFrame) -> Dict[str, float]:
    comp = {}
    n = len(df)
    for c in df.columns:
        non_missing = int(df[c].notna().sum())
        comp[c] = float(non_missing) / n if n > 0 else 0.0
    return comp

def _completeness_score(per_col: Dict[str, float], weights: Dict[str, float] = None) -> (float, Dict[str, Any]):
    if not per_col:
        return 1.0, {"per_column": {}, "n_columns": 0}
    cols = list(per_col.keys())
    if weights is None:
        weights = {c: 1.0 for c in cols}
    total_weight = sum(weights.get(c, 1.0) for c in cols)
    if total_weight == 0:
        return 0.0, {"per_column": per_col, "n_columns": len(cols)}
    agg = sum(per_col[c] * weights.get(c, 1.0) for c in cols) / total_weight
    return float(agg), {"per_column": per_col, "n_columns": len(cols)}

def _consistency_score(df: pd.DataFrame) -> (float, Dict[str, Any]):
    per_col = {}
    for c in df.columns:
        ser = df[c]
        non_null_count = int(ser.notna().sum())
        if non_null_count == 0:
            per_col[c] = 1.0
            continue
        if pd.api.types.is_numeric_dtype(ser):
            per_col[c] = 1.0
            continue
        coerced = pd.to_numeric(ser, errors="coerce")
        numeric_ok = int(coerced.notna().sum())
        if numeric_ok / non_null_count >= 0.8:
            per_col[c] = float(numeric_ok) / non_null_count
            continue
        top_counts = ser.dropna().astype(str).value_counts()
        if top_counts.empty:
            per_col[c] = 1.0
        else:
            top1 = int(top_counts.iloc[0])
            per_col[c] = float(top1) / non_null_count
    score = float(np.mean(list(per_col.values()))) if per_col else 1.0
    return score, {"per_column": per_col}

def _semantic_score(df: pd.DataFrame) -> (float, Dict[str, Any]):
    per_col = {}
    for c in df.columns:
        ser = df[c].dropna()
        if ser.empty:
            per_col[c] = 1.0
            continue
        name = c.lower()
        if "email" in name or ser.astype(str).str.contains("@").any():
            total = len(ser)
            valid = int(ser.astype(str).apply(lambda s: bool(_email_re.match(s))).sum())
            per_col[c] = float(valid) / total if total else 1.0
            continue
        if "date" in name or "time" in name or "timestamp" in name:
            parsed = pd.to_datetime(ser.astype(str), errors="coerce", infer_datetime_format=True)
            total = len(ser)
            ok = int(parsed.notna().sum())
            per_col[c] = float(ok) / total if total else 1.0
            continue
        if "age" in name or c.lower() in ("age", "years"):
            coerced = pd.to_numeric(ser, errors="coerce")
            total = len(ser)
            ok = int(coerced.dropna().between(0, 120).sum())
            per_col[c] = float(ok) / total if total else 1.0
            continue
        per_col[c] = 1.0
    score = float(np.mean(list(per_col.values()))) if per_col else 1.0
    return score, {"per_column": per_col}

def _joinability_score(df: pd.DataFrame) -> (float, Dict[str, Any]):
    n = len(df)
    if n == 0:
        return 0.0, {"best_key": None, "best_score": 0.0}
    candidates = [c for c in df.columns if any(k in c.lower() for k in ("id", "uid", "user_id", "order_id", "uuid"))]
    best_score = 0.0
    best_col = None
    for c in candidates:
        non_null = int(df[c].notna().sum())
        unique = int(df[c].nunique(dropna=True))
        if non_null == 0:
            continue
        score = float(unique) / non_null
        if score > best_score:
            best_score = score
            best_col = c
    return float(best_score), {"best_key": best_col, "best_score": best_score, "candidates_examined": candidates}

def _safety_score(df: pd.DataFrame) -> (float, Dict[str, Any]):
    total_cells = 0
    pii_cells = 0
    per_column = {}
    for c in df.columns:
        ser = df[c].dropna().astype(str)
        non_null = int(len(ser))
        total_cells += non_null
        if non_null == 0:
            per_column[c] = {"pii_count": 0, "non_null": 0}
            continue
        email_count = int(ser.apply(lambda s: bool(_email_re.match(s))).sum())
        phone_count = int(ser.apply(lambda s: bool(_phone_re.search(s))).sum())
        ssn_count = int(ser.apply(lambda s: bool(_ssn_re.match(s))).sum())
        col_pii = int(email_count + phone_count + ssn_count)
        pii_cells += col_pii
        per_column[c] = {"pii_count": col_pii, "non_null": non_null}
    if total_cells == 0:
        return 1.0, {"per_column": per_column, "total_pii": 0, "total_cells": 0}
    score = max(0.0, 1.0 - (pii_cells / total_cells))
    return float(score), {"per_column": per_column, "total_pii": int(pii_cells), "total_cells": int(total_cells)}

def compute_quality_scores(df: pd.DataFrame, profile: Dict[str, Any] = None, issues: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Normalize missing values to ensure empty strings and NaN are treated consistently
    df_normalized = _normalize_missing_values(df)
    
    per_col_completeness = _col_completeness(df_normalized)
    completeness, completeness_detail = _completeness_score(per_col_completeness)

    consistency, consistency_detail = _consistency_score(df_normalized)
    semantic, semantic_detail = _semantic_score(df_normalized)
    joinability, joinability_detail = _joinability_score(df_normalized)
    safety, safety_detail = _safety_score(df_normalized)

    components = {
        "completeness": {"score": round(float(completeness), 4), "detail": completeness_detail},
        "consistency": {"score": round(float(consistency), 4), "detail": consistency_detail},
        "semantic": {"score": round(float(semantic), 4), "detail": semantic_detail},
        "joinability": {"score": round(float(joinability), 4), "detail": joinability_detail},
        "safety": {"score": round(float(safety), 4), "detail": safety_detail},
    }
    overall = float(np.mean([components[k]["score"] for k in components]))
    result = {
        "components": components,
        "overall_score": round(float(overall), 4),
        "overall_percent": round(float(overall) * 100, 2)
    }
    return result
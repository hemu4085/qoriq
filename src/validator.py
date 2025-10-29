"""
Issue detector for Qoriq v1.0.

detect_issues(df, missing_threshold) returns a list of issues where each issue is a dict:
{
  "title": str,
  "type": str,
  "severity": "low|medium|high",
  "columns": [colnames],
  "description": str,
  "suggested_fix": str
}
"""
from typing import List, Dict, Any
import pandas as pd
import numpy as np
import re

_email_re = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")

def _high_missing(df: pd.DataFrame, thresh: float) -> List[Dict[str, Any]]:
    issues = []
    for c in df.columns:
        pct = df[c].isna().mean() if len(df) > 0 else 0.0
        if pct >= thresh and pct > 0:
            issues.append({
                "title": f"High missing rate in column '{c}'",
                "type": "missing_high",
                "severity": "high" if pct >= 0.5 else "medium",
                "columns": [c],
                "description": f"Column '{c}' has {pct:.2%} missing values ({int(df[c].isna().sum())} missing).",
                "suggested_fix": "Consider filling missing values, dropping rows, or imputing (median for numeric / empty or mode for categorical)."
            })
    return issues

def _duplicates(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    candidate_id_cols = [c for c in df.columns if c.lower() in ("id", "user_id", "userid")]
    for c in candidate_id_cols:
        if c in df.columns:
            ndup = int(df.duplicated(subset=[c]).sum())
            if ndup > 0:
                issues.append({
                    "title": f"Duplicate values in id column '{c}'",
                    "type": "duplicate_rows",
                    "severity": "high",
                    "columns": [c],
                    "description": f"Column '{c}' has {ndup} duplicate rows.",
                    "suggested_fix": "Investigate duplicates; consider deduplicating by keeping the most recent or aggregated record."
                })
    return issues

def _dtype_mismatch(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    n = len(df)
    for c in df.columns:
        ser = df[c]
        if pd.api.types.is_numeric_dtype(ser):
            continue
        # attempt to coerce values to numeric for columns that are mostly numeric
        coerced = pd.to_numeric(ser, errors="coerce")
        num_non_na = int(coerced.notna().sum())
        if n > 0 and (num_non_na / n) >= 0.8 and num_non_na < n:
            issues.append({
                "title": f"Possible numeric column stored as object '{c}'",
                "type": "dtype_mismatch",
                "severity": "medium",
                "columns": [c],
                "description": f"Column '{c}' looks mostly numeric ({num_non_na}/{n} values) but contains non-numeric entries.",
                "suggested_fix": "Coerce column to numeric and inspect non-numeric rows; fix formatting (commas, currency symbols) or missing markers."
            })
    return issues

def _invalid_emails(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    for c in df.columns:
        ser = df[c]
        if ser.dtype == object and ser.dropna().astype(str).str.contains("@").any():
            total = len(ser.dropna())
            if total == 0:
                continue
            valid = int(ser.dropna().astype(str).apply(lambda s: bool(_email_re.match(s))).sum())
            invalid = total - valid
            if invalid > 0:
                issues.append({
                    "title": f"Invalid email addresses in '{c}'",
                    "type": "invalid_email",
                    "severity": "medium" if invalid/total < 0.2 else "high",
                    "columns": [c],
                    "description": f"Column '{c}' has {invalid}/{total} invalid-looking email values.",
                    "suggested_fix": "Validate emails, remove or correct invalid addresses, or mask them if PII-sensitive."
                })
    return issues

def _date_parse_issues(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    for c in df.columns:
        ser = df[c]
        if ser.dtype == object:
            sample = ser.dropna().astype(str).head(200)
            if sample.empty:
                continue
            parsed = pd.to_datetime(sample, errors="coerce")
            n_parsed = int(parsed.notna().sum())
            if n_parsed > 0 and n_parsed < len(sample):
                issues.append({
                    "title": f"Column '{c}' contains partially parseable dates",
                    "type": "date_partial_parse",
                    "severity": "medium",
                    "columns": [c],
                    "description": f"Column '{c}' had {n_parsed}/{len(sample)} sample values parseable as dates.",
                    "suggested_fix": "Standardize date formats or provide parsing rules when importing."
                })
    return issues

def _constant_columns(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    for c in df.columns:
        if df[c].nunique(dropna=True) <= 1:
            issues.append({
                "title": f"Constant or near-constant column '{c}'",
                "type": "constant_column",
                "severity": "low",
                "columns": [c],
                "description": f"Column '{c}' has {df[c].nunique(dropna=True)} unique values.",
                "suggested_fix": "Drop this column if it provides no signal for modeling."
            })
    return issues

def _outliers(df: pd.DataFrame) -> List[Dict[str, Any]]:
    issues = []
    numeric = df.select_dtypes(include=[np.number])
    for c in numeric.columns:
        ser = numeric[c].dropna()
        if len(ser) < 5:
            continue
        mean = ser.mean()
        std = ser.std()
        if std == 0 or pd.isna(std):
            continue
        z = (ser - mean).abs() / std
        n_out = int((z > 4).sum())
        if n_out > 0:
            issues.append({
                "title": f"Extreme outliers in '{c}'",
                "type": "outliers",
                "severity": "medium",
                "columns": [c],
                "description": f"Column '{c}' has {n_out} values with |z| > 4.",
                "suggested_fix": "Inspect outliers; consider winsorizing, clipping, or imputing if they are erroneous."
            })
    return issues

def detect_issues(df: pd.DataFrame, missing_threshold: float = 0.2) -> List[Dict[str, Any]]:
    out = []
    out.extend(_high_missing(df, missing_threshold))
    out.extend(_duplicates(df))
    out.extend(_dtype_mismatch(df))
    out.extend(_invalid_emails(df))
    out.extend(_date_parse_issues(df))
    out.extend(_constant_columns(df))
    out.extend(_outliers(df))
    # Remove duplicate issues by (title, columns)
    seen = set()
    uniq = []
    for it in out:
        key = (it.get("title"), tuple(it.get("columns", [])))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(it)
    return uniq
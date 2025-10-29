# Conservative helper additions for the fixer to avoid introducing new nulls.
# This file adds a non-invasive helper _safe_coerce_dates that the fixer can
# use when coercing date-like columns. It deliberately preserves original
# values when parsing fails so we don't increase null counts unexpectedly.
import pandas as pd
import numpy as np
from typing import Any

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
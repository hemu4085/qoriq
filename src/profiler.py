"""
Simple profiler for Qoriq v1.0.

Computes:
- number of rows / columns
- per-column dtype, missing counts / rate
- numeric stats (min, max, mean, std)
- top_k values for non-numeric columns
Returns a JSON-serializable dict.
"""
from typing import Dict, Any
import pandas as pd
import numpy as np

def profile_dataframe(df: pd.DataFrame, top_k: int = 10) -> Dict[str, Any]:
    report = {
        "n_rows": int(len(df)),
        "n_columns": int(df.shape[1]),
        "columns": {}
    }
    for col in df.columns:
        series = df[col]
        col_report = {
            "dtype": str(series.dtype),
            "n_missing": int(series.isna().sum()),
            "pct_missing": float(series.isna().mean() if len(series) > 0 else 0.0),
        }
        if pd.api.types.is_numeric_dtype(series):
            if series.dropna().empty:
                col_report.update({"min": None, "max": None, "mean": None, "std": None})
            else:
                col_report.update({
                    "min": float(series.min()),
                    "max": float(series.max()),
                    "mean": float(series.mean()),
                    "std": float(series.std()),
                })
            col_report["n_unique"] = int(series.nunique(dropna=True))
        else:
            top = series.dropna().astype(str).value_counts().head(top_k).to_dict()
            col_report["top_values"] = {str(k): int(v) for k, v in top.items()}
            col_report["n_unique"] = int(series.nunique(dropna=True))
        report["columns"][str(col)] = col_report
    return report
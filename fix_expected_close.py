# file: fix_expected_close.py
# Use this standalone script to standardize the `expected_close` column in a CSV,
# show before/after samples and a summary of changed values.
#
# Usage:
#   python fix_expected_close.py path/to/your_file.csv
#
# Output:
#   - prints counts and sample of before/after changes
#   - writes a file named <orig>_expected_close_fixed.csv (in same folder) if you want to keep the cleaned file

import sys
import os
import pandas as pd

def standardize_expected_close(series: pd.Series) -> pd.Series:
    """
    Attempt to parse various date formats and standardize to ISO date string YYYY-MM-DD.
    If parsing fails for a value, result will be NaT (kept as None in exported CSV).
    """
    # coerce common 'NA' or similar markers to NaN
    ser = series.replace({"": None, "NA": None, "N/A": None, "null": None})
    # Try direct pandas parsing with infer format
    parsed = pd.to_datetime(ser.astype(str), errors="coerce", infer_datetime_format=True, dayfirst=False)
    # For cases where dayfirst is True (e.g., "15/02/2021"), try again with dayfirst=True for remaining NaT
    mask_not_parsed = parsed.isna() & ser.notna()
    if mask_not_parsed.any():
        parsed_alt = pd.to_datetime(ser[mask_not_parsed].astype(str), errors="coerce", infer_datetime_format=True, dayfirst=True)
        parsed.loc[mask_not_parsed] = parsed_alt
    # Return as ISO date strings for stable text output; keep NaT as None
    return parsed.dt.date.astype("object").where(parsed.notna(), None)

def main(path):
    if not os.path.exists(path):
        print("File not found:", path)
        return
    df = pd.read_csv(path, dtype=str)  # read as strings to preserve raw inputs
    col = "expected_close"
    if col not in df.columns:
        print(f"Column '{col}' not found in file. Existing columns: {list(df.columns)}")
        return

    before = df[col].copy()
    after = standardize_expected_close(before)

    # Compare
    before_repr = before.fillna("<<NA>>").astype(str)
    after_repr = pd.Series(after).fillna("<<NA>>").astype(str)
    changed_mask = ~before_repr.eq(after_repr)
    n_changed = int(changed_mask.sum())
    n_total = len(df)

    print(f"Standardizing column '{col}'")
    print(f"Total rows: {n_total}")
    print(f"Rows with changed value in '{col}': {n_changed}")

    # show up to 10 sample changed rows
    sample_idx = list(df[changed_mask].head(10).index)
    if sample_idx:
        print("\nSample before -> after (up to 10 rows):")
        for i in sample_idx:
            print(f"row {i}: '{before.iloc[i]}'  ->  '{after.iloc[i]}'")
    else:
        print("\nNo changes detected in sample window (values already standardized or not parseable).")

    # If you want to overwrite or save cleaned file:
    out_path = os.path.splitext(path)[0] + "_expected_close_fixed.csv"
    df_clean = df.copy()
    df_clean[col] = after  # object dtype, with None for missing
    df_clean.to_csv(out_path, index=False)
    print(f"\nWrote cleaned file to: {out_path}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python fix_expected_close.py path/to/file.csv")
    else:
        main(sys.argv[1])
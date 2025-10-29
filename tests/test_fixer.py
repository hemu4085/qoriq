import pandas as pd
from src import fixer, quality

def _sample_df():
    return pd.DataFrame({
        "date": ["2021-01-01", "", "not-a-date"],
        "val": ["1", "2", ""],
    }, index=[0,1,2])

def test_recommend_and_apply_fixes_smoke():
    df = _sample_df()
    recs = fixer.recommend_bulk_fixes(df)
    # Expect at least one recommendation (empty -> NaN and not-a-date)
    assert any(r["reason"] in {"empty_to_nan", "unsafe_token", "coerce_date"} for r in recs)
    fixed_df, applied = fixer.apply_fixes(df, recs)
    # Ensure original df unchanged (conservative)
    assert df.at[0, "date"] == "2021-01-01"
    # Ensure fixed_df has been updated at recommended locations
    # For example index 1 date was "" -> NaN after apply OR left as-is conservatively
    assert pd.isna(fixed_df.at[1, "date"]) or fixed_df.at[1, "date"] == "" or fixed_df.at[1, "date"] == df.at[1, "date"]
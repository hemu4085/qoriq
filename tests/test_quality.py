import pandas as pd
import pytest
from src import quality

def _make_test_df():
    return pd.DataFrame({
        "a": ["2020-01-01", "", "not-a-date"],
        "b": ["x", "y", ""],
    })

def test_default_quality_unchanged():
    df = _make_test_df()
    # ensure defaults restored to initial defaults
    quality.set_scoring_weights({"completeness": 0.5, "safety": 0.5})
    metrics = quality.score_dataframe(df)
    total = 6
    non_missing = 4
    completeness_expected = 100.0 * (non_missing / total)
    safety_expected = 100.0 * ((total - 1) / total)
    quality_expected = (completeness_expected + safety_expected) / 2.0
    assert pytest.approx(metrics["completeness"], rel=1e-3) == completeness_expected
    assert pytest.approx(metrics["safety"], rel=1e-3) == safety_expected
    assert pytest.approx(metrics["quality"], rel=1e-3) == quality_expected

def test_weights_override_all_dimensions():
    df = _make_test_df()
    # make completeness only contribute
    quality.set_scoring_weights({"completeness": 1.0, "safety": 0.0,
                                 "consistency": 0.0, "uniqueness": 0.0,
                                 "validity": 0.0, "timeliness": 0.0})
    metrics = quality.score_dataframe(df)
    assert pytest.approx(metrics["quality"], rel=1e-3) == metrics["completeness"]
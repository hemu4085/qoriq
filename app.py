#!/usr/bin/env python3
"""
Qoriq Streamlit app — bulk fixes + before/after and DQ recompute

This app:
- Upload or load sample CSV
- Show Data Preview, Profiling, Detected Issues, Data Quality Score (before)
- Offer "Apply bulk fixes" to automatically fix all detected issues in bulk
- Show cleaned preview, change summary, removed rows, changed-row diffs
- Recompute Profiling and Data Quality Score (after) and show deltas
- Allow download of cleaned CSV and manifest (contains before/after scores and summary)
"""
import os
import json
import streamlit as st
import pandas as pd
import altair as alt

# Import qoriq modules
try:
    from src.profiler import profile_dataframe
    from src.validator import detect_issues
    from src.quality import compute_quality_scores
    from src.fixer import generate_naive_clean_with_summary
except Exception as e:
    st.error(f"Could not import Qoriq modules: {e}. Ensure src/ is on PYTHONPATH and contains required modules.")
    st.stop()

st.set_page_config(page_title="Qoriq — Data Readiness", layout="wide")
st.title("Qoriq — Data Readiness — Bulk Fixes (v1.x)")
st.markdown("Upload CSV or load sample → review profiling, issues and DQ score → apply bulk fixes → inspect cleaned dataset and updated DQ score.")

# Sidebar controls
st.sidebar.header("Input")
use_sample = st.sidebar.button("Load sample dataset")
uploaded_file = st.sidebar.file_uploader("Upload CSV file", type=["csv"])
show_raw = st.sidebar.checkbox("Show raw data preview", value=True)
missing_threshold = st.sidebar.slider("Missingness threshold to flag (pct)", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
max_preview_rows = st.sidebar.number_input("Max preview changed rows", min_value=10, max_value=1000, value=200, step=10)
output_dir = st.sidebar.text_input("Output directory", value="./qoriq_output")

# Load or upload dataset
df = None
sample_path = os.path.join("examples", "sample_data", "sample_users.csv")
if use_sample:
    if os.path.exists(sample_path):
        df = pd.read_csv(sample_path)
        st.sidebar.success("Loaded sample dataset")
    else:
        st.sidebar.error("Sample file not found.")
elif uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.sidebar.success(f"Loaded uploaded file: {uploaded_file.name}")
    except Exception as e:
        st.sidebar.error(f"Failed to read uploaded CSV: {e}")

if df is None:
    st.info("No dataset loaded. Upload a CSV or load the sample dataset.")
    st.stop()

# Show raw preview
if show_raw:
    st.subheader("Data preview (first 200 rows)")
    st.dataframe(df.head(200))

# Profiling & issues (before)
st.subheader("Profiling (Before fixes)")
profile_before = profile_dataframe(df, top_k=10)
st.write(f"Rows: **{profile_before.get('n_rows')}**, Columns: **{profile_before.get('n_columns')}**")
cols = profile_before.get("columns", {})
summary_rows = []
for c, m in cols.items():
    summary_rows.append({
        "column": c,
        "dtype": m.get("dtype"),
        "n_missing": m.get("n_missing"),
        "pct_missing": round(m.get("pct_missing", 0.0), 3),
        "n_unique": m.get("n_unique", "")
    })
st.dataframe(pd.DataFrame(summary_rows), use_container_width=True)

st.subheader("Detected issues (Before fixes)")
issues = detect_issues(df, missing_threshold=missing_threshold)
if not issues:
    st.success("No issues detected.")
else:
    st.write(f"Found {len(issues)} issue(s).")
    for i, it in enumerate(issues, start=1):
        st.markdown(f"**{i}. {it.get('title','Issue')}**")
        st.write(f"- Severity: **{it.get('severity','medium')}**")
        st.write(f"- Column(s): {it.get('columns')}")
        st.write(f"- Description: {it.get('description')}")
        if it.get("suggested_fix"):
            st.info(f"Suggested fix: {it.get('suggested_fix')}")
        st.write("---")

# Data Quality Score (Before)
dq_before = compute_quality_scores(df, profile_before, issues)
st.subheader("Data Quality (Before fixes)")
st.metric("Overall Data Quality", f"{dq_before['overall_percent']}%")
comp_list = [{"component": k.capitalize(), "score": float(v["score"]) * 100} for k, v in dq_before["components"].items()]
comp_df = pd.DataFrame(comp_list)
bar = alt.Chart(comp_df).mark_bar().encode(x="score:Q", y=alt.Y("component:N", sort='-x'), color="score:Q")
st.altair_chart(bar.properties(height=220), use_container_width=True)

# Bulk fix action
st.markdown("### Fix the detected issues (bulk, automatic)")
apply_fixes = st.button("Apply bulk fixes to all detected issues")
if apply_fixes:
    with st.spinner("Applying bulk fixes..."):
        cleaned_df, summary, changes_df, removed_rows_df = generate_naive_clean_with_summary(df, issues, max_preview_rows=int(max_preview_rows))

    st.success("Bulk fixes applied (preview below).")

    # Show change summary
    st.subheader("Change summary")
    st.json(summary)

    # Show per-column changed counts (if any)
    if summary.get("per_column_changed"):
        st.markdown("**Per-column changed counts (full dataset)**")
        per_col = summary["per_column_changed"]
        st.dataframe(pd.DataFrame([{"column": k, "changed_count": v} for k, v in per_col.items()]), use_container_width=True)
    else:
        st.info("No per-column value changes detected across full dataset.")

    # Show removed rows due to dedup
    if not removed_rows_df.empty:
        st.markdown(f"**Rows removed by dedupe — {len(removed_rows_df)} rows**")
        st.dataframe(removed_rows_df, use_container_width=True)

    # Show changed-row preview diffs
    if not changes_df.empty:
        st.markdown(f"**Preview of changed rows (showing before/after for changed cells) — returned {len(changes_df)} rows**")
        st.dataframe(changes_df, use_container_width=True)
    else:
        st.info("No changed rows to preview (or changes occurred outside the preview limit).")

    # Show cleaned preview & allow download
    st.subheader("Cleaned data preview (first 200 rows)")
    st.dataframe(cleaned_df.head(200), use_container_width=True)
    csv_bytes = cleaned_df.to_csv(index=False).encode("utf-8")
    st.download_button("Download cleaned CSV", data=csv_bytes, file_name="qoriq_cleaned.csv")

    # Profiling & DQ after fixes
    st.subheader("Profiling (After fixes)")
    profile_after = profile_dataframe(cleaned_df, top_k=10)
    st.write(f"Rows: **{profile_after.get('n_rows')}**, Columns: **{profile_after.get('n_columns')}**")
    cols_after = profile_after.get("columns", {})
    summary_rows_after = []
    for c, m in cols_after.items():
        summary_rows_after.append({
            "column": c,
            "dtype": m.get("dtype"),
            "n_missing": m.get("n_missing"),
            "pct_missing": round(m.get("pct_missing", 0.0), 3),
            "n_unique": m.get("n_unique", "")
        })
    st.dataframe(pd.DataFrame(summary_rows_after), use_container_width=True)

    st.subheader("Detected issues (After fixes)")
    issues_after = detect_issues(cleaned_df, missing_threshold=missing_threshold)
    if not issues_after:
        st.success("No issues detected after fixes.")
    else:
        st.write(f"Found {len(issues_after)} issue(s) after fixes.")
        for i, it in enumerate(issues_after, start=1):
            st.markdown(f"**{i}. {it.get('title','Issue')}**")
            st.write(f"- Severity: **{it.get('severity','medium')}**")
            st.write(f"- Column(s): {it.get('columns')}")
            st.write(f"- Description: {it.get('description')}")
            if it.get("suggested_fix"):
                st.info(f"Suggested fix: {it.get('suggested_fix')}")
            st.write("---")

    dq_after = compute_quality_scores(cleaned_df, profile_after, issues_after)
    st.subheader("Data Quality (After fixes)")
    st.metric("Overall Data Quality (Before → After)", f"{dq_before['overall_percent']}% → {dq_after['overall_percent']}%")

    comp_list_after = [{"component": k.capitalize(), "before": float(dq_before["components"][k]["score"]) * 100, "after": float(v["score"]) * 100} for k, v in dq_after["components"].items()]
    comp_df_delta = pd.DataFrame(comp_list_after)
    st.dataframe(comp_df_delta, use_container_width=True)

    # Save manifest (optional)
    manifest = {
        "original_profile": profile_before,
        "original_issues": issues,
        "original_dq": dq_before,
        "cleaned_profile": profile_after,
        "cleaned_issues": issues_after,
        "cleaned_dq": dq_after,
        "change_summary": summary
    }
    manifest_json = json.dumps(manifest, indent=2, default=str)
    st.download_button("Download manifest (before/after + summary)", data=manifest_json, file_name="qoriq_manifest_before_after.json")

    # Optionally save to output_dir on disk
    if st.sidebar.button("Save cleaned CSV & manifest to output dir"):
        try:
            os.makedirs(output_dir, exist_ok=True)
            cleaned_path = os.path.join(output_dir, "qoriq_cleaned.csv")
            manifest_path = os.path.join(output_dir, "qoriq_manifest_before_after.json")
            cleaned_df.to_csv(cleaned_path, index=False)
            with open(manifest_path, "w") as f:
                f.write(manifest_json)
            st.sidebar.success(f"Wrote cleaned CSV and manifest to {output_dir}")
        except Exception as e:
            st.sidebar.error(f"Failed to save outputs: {e}")
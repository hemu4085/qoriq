#!/usr/bin/env python3
"""
Qoriq v1.1 Streamlit app: upload CSV or load sample, profile, detect issues, compute DQ scores.

Run:
  pip install -r requirements.txt
  streamlit run app.py
"""
import os
import json
from typing import Dict, Any, List
import streamlit as st
import pandas as pd
import altair as alt
import re

# Import qoriq modules
try:
    from src.profiler import profile_dataframe
    from src.validator import detect_issues
    from src.quality import compute_quality_scores
except Exception as e:
    st.error(f"Could not import Qoriq modules: {e}. Ensure src/ is on PYTHONPATH and contains profiler.py, validator.py and quality.py.")
    st.stop()

st.set_page_config(page_title="Qoriq — Data Readiness", layout="wide")
st.title("Qoriq — Data Readiness (Version 1.0)")
st.markdown("Upload a CSV or load the sample. The app profiles the dataset, lists issues, and computes Data Quality scores (Completeness, Consistency, Semantic, Joinability, Safety).")

# Sidebar
st.sidebar.header("Input")
if "loaded" not in st.session_state:
    st.session_state["loaded"] = False
use_sample = st.sidebar.button("Load sample dataset")
uploaded_file = st.sidebar.file_uploader("Upload CSV file", type=["csv"])
show_raw = st.sidebar.checkbox("Show raw data preview", value=True)
missing_threshold = st.sidebar.slider("Missingness threshold to flag (pct)", min_value=0.0, max_value=1.0, value=0.2, step=0.05)
output_dir = st.sidebar.text_input("Output directory", value="./qoriq_output")

# Prepare dataframe
df = None
sample_path = os.path.join("examples", "sample_data", "sample_users.csv")
if use_sample:
    if not os.path.exists(sample_path):
        st.sidebar.error(f"Sample dataset not found at {sample_path}")
    else:
        df = pd.read_csv(sample_path)
        st.sidebar.success("Loaded sample dataset")
        st.session_state["loaded"] = True
elif uploaded_file is not None:
    try:
        df = pd.read_csv(uploaded_file)
        st.sidebar.success(f"Loaded uploaded file: {uploaded_file.name}")
        st.session_state["loaded"] = True
    except Exception as e:
        st.sidebar.error(f"Failed to read uploaded CSV: {e}")

if not st.session_state["loaded"]:
    st.info("No dataset loaded. Use the sidebar to upload a CSV or press 'Load sample dataset'.")
    st.stop()

# Show raw preview
if show_raw:
    st.subheader("Data preview")
    st.dataframe(df.head(200))

# Profiling
st.subheader("Profiling")
with st.spinner("Profiling dataset..."):
    profile = profile_dataframe(df, top_k=10)
st.write(f"Rows: **{profile.get('n_rows')}**, Columns: **{profile.get('n_columns')}**")

# Column summary
cols = profile.get("columns", {})
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

# Issues
st.subheader("Detected issues")
with st.spinner("Analyzing issues..."):
    issues = detect_issues(df, missing_threshold=missing_threshold)

if not issues:
    st.success("No issues detected (for the checks enabled).")
else:
    st.write(f"Found {len(issues)} issue(s).")
    for i, it in enumerate(issues, start=1):
        st.markdown(f"**{i}. {it.get('title', 'Issue')}**")
        st.write(f"- Severity: **{it.get('severity','medium')}**")
        st.write(f"- Column(s): {it.get('columns')}")
        st.write(f"- Description: {it.get('description')}")
        if it.get("suggested_fix"):
            st.info(f"Suggested fix: {it.get('suggested_fix')}")
        st.write("---")

# Data Quality scoring
st.subheader("Data Quality Scores")
with st.spinner("Computing scores..."):
    dq = compute_quality_scores(df, profile=profile, issues=issues)

components = dq["components"]
overall_pct = dq["overall_percent"]
st.metric("Overall Data Quality", f"{overall_pct}%")

# Component bars
comp_list = []
for k, v in components.items():
    comp_list.append({"component": k.capitalize(), "score": float(v["score"]) * 100})
comp_df = pd.DataFrame(comp_list)

bar = alt.Chart(comp_df).mark_bar().encode(
    x=alt.X("score:Q", title="Score (%)"),
    y=alt.Y("component:N", sort='-x', title="Component"),
    color=alt.Color("score:Q", scale=alt.Scale(scheme="greens"))
).properties(height=220)

text = alt.Chart(comp_df).mark_text(
    align='left',
    baseline='middle',
    dx=3
).encode(
    x=alt.X('score:Q'),
    y=alt.Y('component:N'),
    text=alt.Text('score:Q', format=".1f")
)

st.altair_chart(bar + text, use_container_width=True)

# DQ details
with st.expander("DQ score details and breakdown"):
    for k, v in components.items():
        st.subheader(k.capitalize())
        st.write(f"Score: **{v['score']*100:.2f}%**")
        st.write("Detail:")
        st.json(v.get("detail", {}))

# Export manifest
st.subheader("Export")
manifest = {
    "rows": int(len(df)),
    "columns": int(df.shape[1]),
    "issues_count": len(issues),
    "issues": issues,
    "data_quality": dq,
    "profile": profile
}
manifest_json = json.dumps(manifest, indent=2, default=str)
st.download_button("Download manifest (JSON)", data=manifest_json, file_name="qoriq_manifest.json")

# Simple naive cleaner and download
def generate_naive_clean(df: pd.DataFrame, issues: List[Dict[str, Any]]) -> pd.DataFrame:
    dfc = df.copy()
    for it in issues:
        if it.get("type") == "missing_high" and it.get("columns"):
            for c in it["columns"]:
                if c not in dfc.columns:
                    continue
                if pd.api.types.is_numeric_dtype(dfc[c]):
                    med = dfc[c].median(skipna=True)
                    dfc[c] = dfc[c].fillna(med)
                else:
                    dfc[c] = dfc[c].fillna("")
        if it.get("type") == "invalid_email":
            for c in it["columns"]:
                if c not in dfc.columns:
                    continue
                dfc[c] = dfc[c].where(dfc[c].astype(str).apply(lambda s: bool(re.match(r'^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$', str(s)))), "")
        if it.get("type") == "duplicate_rows":
            cols_dup = it.get("columns", [])
            if cols_dup:
                dfc = dfc.drop_duplicates(subset=cols_dup, keep="first")
    return dfc

if st.button("Generate naive cleaned CSV (preview)"):
    with st.spinner("Applying naive fixes..."):
        cleaned = generate_naive_clean(df, issues)
    st.subheader("Cleaned preview")
    st.dataframe(cleaned.head(200))
    csv_bytes = cleaned.to_csv(index=False).encode("utf-8")
    st.download_button("Download cleaned CSV (naive)", data=csv_bytes, file_name="cleaned_dataset.csv")

# Save manifest to output_dir if requested
if st.sidebar.button("Save manifest to output directory"):
    try:
        os.makedirs(output_dir, exist_ok=True)
        manifest_path = os.path.join(output_dir, "qoriq_manifest.json")
        with open(manifest_path, "w") as f:
            f.write(manifest_json)
        st.sidebar.success(f"Wrote manifest to {manifest_path}")
    except Exception as e:
        st.sidebar.error(f"Failed to write manifest: {e}")
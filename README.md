```markdown
# Qoriq — Data Readiness (Version 1.0)

Qoriq is a lightweight, interactive data readiness tool to help prepare CSV data for foundation models, RAG, and other ML/LLM workflows.

Version 1.0 functionality:
- Upload a CSV or load a provided sample CSV.
- Run dataset profiling (schema, missingness, top-values, numeric stats).
- Detect common issues (high missingness, duplicates, dtype mismatches, invalid emails, partial dates, constant columns, outliers).
- Compute Data Quality scores across five categories: Completeness, Consistency, Semantic, Joinability, Safety.
- Display results in an interactive Streamlit UI and allow downloading a manifest (JSON) and a naive cleaned CSV preview.

Quick start
1. Create and activate a Python virtualenv:
   python -m venv .venv
   source .venv/bin/activate   # macOS / Linux
   .venv\Scripts\activate      # Windows (PowerShell)

2. Install dependencies:
   pip install -r requirements.txt

3. Run the app:
   streamlit run app.py

Notes
- This is a v1 prototype focused on CSV upload and sample data. Later versions will add connectors (S3, SQL), guided fixes with before/after diffs, and persistent manifests.
- The scoring and fixes are heuristic and intentionally simple to be explainable and easy to extend.
```
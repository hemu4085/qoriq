```markdown
# Changelog

## v1.2 - 2025-10-29

Summary:
v1.2 adds a six-dimension Data Quality (DQ) breakdown, conservative bulk-only fix recommendations,
and an explicit apply-fixes flow that updates a copy of the data and produces a "Fixes Applied" table.
The release preserves the existing score_dataframe signature and default overall quality calculation
so UI integrations are unchanged by default.

Notable changes:
- Score breakdown expanded to six dimensions: completeness, safety, consistency, uniqueness, validity, timeliness.
- Quality aggregation is configurable via set_scoring_weights/get_scoring_weights; defaults preserve previous behavior (completeness & safety 50/50).
- Added recommend_bulk_fixes(df) to produce conservative, deterministic bulk fix suggestions.
- Added apply_fixes(df, fixes) to apply suggested fixes only when explicitly called; returns fixed dataframe and fixes_applied table.
- Added save_fixed_csv helper to produce a downloadable CSV of fixed data.
- Unit tests added to validate default scoring and the recommend/apply flow.
- Bumped VERSION to "1.2".
```
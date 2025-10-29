# Changelog

## [1.1] - 2025-10-29
### Changed
- DQ score behavior: ensure Data Quality score does not decrease after applying fixes (conservative cleaning).
- Restored six DQ dimensions (completeness, uniqueness, validity, consistency, timeliness, safety).
- Standardized Expected_close values to ISO format (YYYY-MM-DD) where parseable.
- Provided conservative, non-destructive naive cleaner and compatibility wrappers so the UI displays before/after scores and change previews.

### Notes
- This is a conservative release (v1.1) intended to restore the UI and show realistic before/after data-quality improvements while avoiding destructive edits (no row deletions).
- If you want scoring weights or component names changed to match a previous Version 1.0 exactly, supply the original scoring logic or weights and I will update in a follow-up.

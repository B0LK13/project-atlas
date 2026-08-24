# AS-VAL-001 — Freshness + Orphan Validation (package guide)

Backlog **H-006** / **H-007** packaged as **AS-VAL-001**.

## Behavior

`atlas validate` (via `project_atlas.validation.validate`) now runs:

1. **H-006 Freshness** — objective `modified_at` vs injected `reference_now` and `stale_after_days` (default 180).
   - missing → `H-006-unknown` (ERROR; never assumed fresh/stale)
   - corrupt timestamp → `H-006-corrupt` (ERROR; no silent normalization)
   - Unix-epoch / pre-1980 `modified_at` → `H-006-untrusted` (WARNING; missing metadata, not age)
   - quarantined sources are excluded from H-006 portfolio cross-check (AS-SEC-001)
   - objectively stale → `H-006-stale` (WARNING finding)
   - portfolio marks fresh while objectively stale → `H-006-launder` (ERROR)
   - portfolio omits objectively stale source → `H-006-silent` (ERROR)
2. **H-007 Orphan** — Layer B/C notes under `projects/` / `01-portfolio/` with no inbound link, project-bundle membership, or concept-index resource membership → `H-007-orphan` (**WARNING, report-only**).

Findings are returned under `result["findings"]` (deterministic order). Wall-clock never appears in finding payloads.

## Non-goals

- No CLI/schema churn in this package (BACKUP rem soft exclusion)
- No `knowledge_compiler` changes
- No orphan delete/rewrite
- No subjective trust scores

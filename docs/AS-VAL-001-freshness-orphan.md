# AS-VAL-001 — Freshness + Orphan Validation (package guide)

Backlog **H-006** / **H-007** packaged as **AS-VAL-001**.

## Behavior

`atlas validate` (via `project_atlas.validation.validate`) now runs:

1. **H-006 Freshness** — objective `modified_at` vs injected `reference_now` and `stale_after_days` (default 180).
   - missing → `H-006-unknown` (ERROR; never assumed fresh/stale)
   - corrupt timestamp → `H-006-corrupt` (ERROR; no silent normalization)
   - timestamp outside the trusted window → `H-006-untrusted` (WARNING; never
     fresh, never stale). The window is bounded at both ends: epoch/pre-1980
     stamps below, and stamps dated a full day or more after `reference_now`
     above. A future-dated timestamp is not evidence of freshness — its
     freshness state is unknown. Sub-day clock skew stays inside normal
     evaluation, and a future stamp is never clamped to `reference_now`.
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

# Knowledge Time Machine — architecture (PREP)

Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide two complementary read lenses over evidence-backed knowledge:

1. **As-of** — reconstruct the estate view at a declared valid-time *T*
   (and optionally a knowledge/compilation boundary *X*).
2. **Diff (T1→T2)** — deterministic delta between two as-of views for
   **claims**, **graph projections**, and **decision/review dispositions**.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Lenses (UI / Ask / MCP) — consume-only; UI≠canonical       │
├─────────────────────────────────────────────────────────────┤
│  Time Machine service (future)                              │
│    as_of(scope, T[, X]) → AsOfSnapshot                      │
│    diff(scope, T1, T2[, X1, X2]) → KnowledgeDiff            │
├─────────────────────────────────────────────────────────────┤
│  Diff projectors (future)                                   │
│    claim_diff · graph_diff · decision_diff                  │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only)                 │
│    AS-2.0-TEMPORAL-001 windows + as-of                      │
│    AS-CORE-003 claims / conflicts / reviews                 │
│    AS-GRAPH-* derived projections                           │
└─────────────────────────────────────────────────────────────┘
```

## Valid-time vs knowledge-time

| Axis | Meaning | Source today | Time Machine rule |
|---|---|---|---|
| Valid time | When the proposition held in the world | Declared windows / event evidence | Required for as-of *T*; never invent from observation |
| Knowledge time | What compilation *X* knew | Lineage + compile receipts | Optional filter; default = latest compile in scope |
| Query wall-clock | When the operator clicked | Process clock | **Forbidden** as selection input |

## As-of snapshot (conceptual)

An as-of result is a **derived, deterministic** envelope:

- `scope` — project / subject set / estate slice (explicit; no implicit whole-estate)
- `as_of_valid_time` — operator-declared *T* (ISO-like string; not `now`)
- `knowledge_compilation_id` — optional *X*
- `claims[]` — selected or unresolved dispositions per subject/field
- `graph` — optional derived entity/edge projection at *T*
- `decisions[]` — optional review/decision dispositions visible at *T*
- `unresolved[]` — fail-closed leftovers (overlap, incomplete, authority_pending)
- `authority.level = derived`
- `truth_boundary` constant documenting non-authority

Selection reuses AS-2.0-TEMPORAL-001 semantics: single cover → selected;
overlap → unresolved; unknown evidence alone → never selects current.

## Diff (T1→T2)

`diff` materializes three parallel deltas (same scope):

| Diff kind | Unit of change | Notes |
|---|---|---|
| Claim diff | claim_id / subject+field | added · removed · changed · unresolved_delta |
| Graph diff | entity_id / edge_id | derived only; Graph≠authority |
| Decision diff | decision_id / review_id | disposition transitions; not silent approval |

Ordering is deterministic (`sort_keys`, stable id sort). No wall-clock stamps
in generated content (NFR-001).

## Non-goals

- Full bitemporal database / temporal SQL
- Rewriting historical claim values into a single “truth”
- Using graph centrality or LLM similarity as winners
- Authentic estate PILOT evidence from fixtures

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: Time Machine never calls `_promote` / never mutates Layer B

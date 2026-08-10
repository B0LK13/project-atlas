# Temporal / validity UX lens — architecture (PREP)

Package: **AS-2.2-TEMPORAL-UX-PREP-001**  
Status: **PREP ONLY**. Design sketch for Atlas 2.2; does not change 2.1 runtime.

## Intent

Provide a **read-only validity-window + as-of / diff UX cockpit** that surfaces
declared valid-time covers, as-of selection receipts, and T1→T2 lens deltas for
operators / Ask / MCP consumers — without mutating the Core bitemporal spine
or inventing wall-clock “current” as selection input.

## Layers

```text
┌─────────────────────────────────────────────────────────────┐
│  Cockpit / Ask / MCP lenses — consume-only                  │
│  UI ≠ canonical · now ≠ as-of · overlap ≠ silent winner     │
├─────────────────────────────────────────────────────────────┤
│  2.2 Temporal UX service (future AS-2.2-TEMPORAL-001)       │
│    panel(scope, T) → TemporalCockpitView                    │
│    window(claim_id) → ValidityWindowCard                    │
│    receipt(scope, T) → AsOfLensReceipt                      │
│    propose(action) → TemporalAction (fail-closed)           │
├─────────────────────────────────────────────────────────────┤
│  Substrate (already on main — consume only / conceptual)    │
│    AS-2.0-TEMPORAL-001 windows + as-of                      │
│    AS-2.2-TIME-MACHINE-001 as-of / diff stubs               │
│    AS-CORE-003 / AS-CORE-005 claims + temporal safety       │
├─────────────────────────────────────────────────────────────┤
│  Adjacent (do not dual-own)                                 │
│    project_atlas.bitemporal (runtime — consume only)        │
│    AS-2.2-CONFLICT-UX-PREP-001 (unresolved peer UX)         │
│    Graph / decision diffs from time-machine stubs           │
└─────────────────────────────────────────────────────────────┘
```

## Substrate mapping

| Bucket | Source package | Emit path (frozen on main) | Prep rule |
|---|---|---|---|
| Valid-time windows | AS-2.0-TEMPORAL-001 | claim temporal metadata | Consume-only |
| As-of selection | AS-2.0-TEMPORAL-001 / bitemporal | as-of result envelope | Prefer unresolved over wrong current |
| Snapshot / Diff | AS-2.2-TIME-MACHINE-001 | docs stubs under `time-machine/` | UX lens cites; does not fork schema root |
| Authority | AS-CORE-003 | authoritative state records | Consume; never invent trust |

## Cockpit panel (conceptual)

A panel result is a **derived, deterministic** envelope:

- `scope` — explicit project / subject slice (no implicit estate merge)
- `as_of_valid_time` — operator-declared *T* (never `now` / `today`)
- `cards[]` — validity-window cards bound to claim_id
- `receipt` — as-of lens receipt (selected / unresolved / rejected)
- `unresolved[]` — overlap / incomplete / malformed leftovers
- `authority.level = derived`
- `canonical_write = false`
- `wall_clock_input = false`
- `silent_winner = false`
- `atlas_2_1_release_certified = false` on all prep fixtures

Selection reuses AS-2.0-TEMPORAL-001 / Time Machine semantics: single cover →
selected; overlap → unresolved; wall-clock token → rejected_malformed.

## Non-goals

- Mutating `project_atlas.bitemporal` or dual-owning Time Machine contracts
- Full bitemporal database / temporal SQL
- Silent authority winners on overlapping covers
- Subjective trust / confidence scores
- Authentic estate PILOT evidence from fixtures

## Security / safety

- Path-safe synthetic fixture roots only
- Secrets: metadata-only; never embed matched secret content
- Consume-only: temporal UX prep never calls `_promote` / never mutates Layer B
- Evidence refs remain project-scoped

## Deepen PREP

See `AS-2.2-TEMPORAL-UX-DEEPEN-PREP-001.md` and deepen negatives under `fixtures/`.

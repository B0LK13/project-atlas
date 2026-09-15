# AS-INCR-COMPILE-001 — Compiler cache invalidation (tip-safe)

Tip-safe **compiler ops** surface for incremental compilation refresh:

- Deterministic **invalidation keys** over contracted input fingerprints
- **Stale-artifact detection** (recorded key ≠ recomputed key)
- **FR-013**: unchanged combined-hash → **byte-identical no-op**

Package ID: `AS-INCR-COMPILE-001`.

## What this is

Library helpers in `project_atlas.compile_cache` plus schema
`compile-cache-receipt`. Receipts may be written under:

```text
generated/compile-cache/<scope_id>.json
```

Cache hit / skip is **operational metadata only**. It is **not**:

- an authority winner or temporal tip
- a trust / confidence score
- MODEL-001A/B/C composition change
- GRAPH incremental quarantine / projections ownership
- XPROJ-003 duplicate-candidates or XPROJ-004 indexes/conflicts
- an AS-RET-001 rewrite

## Public helpers

| Helper | Role |
|---|---|
| `compute_invalidation_key(...)` | Deterministic SHA-256 key (sorted fingerprints + scope + artifact paths) |
| `combined_fingerprint(...)` | SHA-256 over sorted input fingerprint map (FR-013) |
| `decide_cache_action(...)` | `hit` / `miss` / `stale` / `recompile` / `ambiguous` |
| `evaluate_compile_refresh(...)` | End-to-end tip-safe refresh decision + noop bytes |
| `build_cache_receipt(...)` | Schema-valid receipt (`package: AS-INCR-COMPILE-001`) |
| `write_cache_receipt` / `read_cache_receipt` | Atomic vault I/O under `generated/compile-cache/` |

## Fail-closed rules

- Missing / malformed fingerprint fields → **ambiguous** (abort — never success-skip)
- On-disk key ≠ recomputed key → **stale** (recompile — never stale-as-fresh)
- Unchanged key with divergent candidate bytes → **FR-013 refusal**
- Paths under `generated/graph/`, `generated/xproj/`, `generated/indexes/` → **rejected**
- Secret-shaped notes → metadata-only redaction (NFR-004)
- No `generated.at` wall-clock stamps (NFR-001 / ADR-001)

## Consume-only compilers

Callers may fingerprint settled outputs of `knowledge_compiler` /
`semantic_compiler`. This package does **not** reopen MODEL-001A/B/C
allow-lists, goldens, or writer semantics.

## CLI

Optional dump CLI is **deferred** (soft-serialize vs other `cli.py` writers).

## Tests

```bash
python -m pytest tests/unit/test_as_incr_compile_001_*.py
```

## Stop condition

```text
IMPLEMENTATION COMPLETE — GOVERNOR REQUIRED
AS-REL-001 MUST NOT OPEN
NO SELF-MERGE
```

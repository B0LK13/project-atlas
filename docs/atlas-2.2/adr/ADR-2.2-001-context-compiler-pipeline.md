# ADR-2.2-001 — Context Compiler pipeline stages

| Field | Value |
|---|---|
| Status | **Proposed (PREP)** — not production-accepted |
| Date | 2026-08-10 |
| Package | AS-2.2-CTX-COMPILER-001 |
| Baseline tip | `a1e0972` / TREE `c6cfe95` |
| Unlock | After `v2.1.0` + `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED` |

## Context

Atlas already ships fixture-safe context packs (`AS-2.0-CTX-001`) and Core
authority / freshness / conflict machinery. North-star analysis identifies a
**Context Compiler** gap: task-specific selection through authority, freshness,
conflicts, and budget — not a static pack dump.

Pre-`v2.1.0` work must remain architecture/contracts/fixtures only so 2.1 tip
stability is preserved.

## Decision

1. **Adopt a fixed pipeline order** for future implementation:

   `task → candidates → authority → freshness → conflicts → budget → package`

   with optional derived stages `relevance` and `privacy` that cannot reorder
   authority evaluation ahead of conflict filtering.

2. **Separate Compiler from CTX-001 packs.** CTX-001 remains the thin
   fixture-safe pack contract. The Compiler emits a richer package that
   *includes* provenance pointers plus per-item reason/authority/freshness and
   a pipeline receipt. Do not relabel CTX-001 as the Compiler.

3. **Derived-only writes.** Future runtime may write under
   `generated/context-compiler/` (name TBD) as derived artifacts. It must not
   mutate Layer B claims, authority records, or call `_promote`.

4. **Fail closed on governance violations:** invent-estate flag, unknown
   profile, secret-scan hit, authority spoof, hard budget overflow (when
   configured), and malformed markers.

5. **No subjective trust scores.** Use objective Core signals only.

## Consequences

### Positive

- Clear sole-writer boundary for post-unlock implementation
- Compatible with hybrid retrieval + Agent OS consumers
- Preserves Truth Core invariants (LLM ≠ authority, graph ≠ authority)

### Negative / deferred

- Schema IDs and module paths remain drafts until freeze review
- Production CLI not authorized in this PREP
- Evaluation harness / ADV corpus deferred to post-unlock package waves

## Alternatives considered

| Alternative | Why rejected |
|---|---|
| Extend CTX-001 schema in place pre-2.1 | Risks 2.1 tip / compat churn |
| LLM-only ranking as authority | Violates LLM ≠ authority |
| Collapse conflicts to highest authority silently | Violates Core conflict review model |

## References

- `docs/atlas-2.2/ctx-compiler/ARCHITECTURE.md`
- `docs/AS-2.0-CTX-001.md`
- `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`
- Gap register `GAP-NS-002`

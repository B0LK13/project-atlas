# ADR-2.2-DOC-CHARTER-001 — Charter + maturity matrix prep boundary

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-DOC-CHARTER-PREP-001 |
| Production slot | AS-2.2-DOC-CHARTER-001 (post-unlock) |
| Date | 2026-08-10 |

## Context

Atlas 2.2 intelligence work requires a **charter** and **maturity matrix**
analogous to Atlas 2.1 (`docs/atlas-2.1/CHARTER.md`,
`FEATURE-MATURITY-MATRIX.md`). The strategy roadmap designates
`AS-2.2-DOC-CHARTER-001` as the **first READY** package after unlock.

The prior 2.2 prep charter was a short boundary stub (~40 lines). Multiple
landed PREP packages (#159–#197) lack a consolidated maturity inventory.
Release certification is **not** complete:

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO
```

## Decision

1. Deepen `docs/atlas-2.2/CHARTER.md` with goals, vocabulary, DAG summary, and gates.
2. Add `docs/atlas-2.2/doc-charter/**` as the PREP home for matrix draft,
   contract stubs, and fixture sketches.
3. Publish `FEATURE-MATURITY-MATRIX.md` as a **draft** only — not release cert.
4. Land presence tests only; do **not** mutate `src/` or promote stub schemas.
5. Do **not** edit `docs/atlas-2.2/README.md` (index owned by sibling worker).

## Consequences

- Auditors have a single charter + matrix draft for landed 2.2 PREP packages.
- Post-unlock `AS-2.2-DOC-CHARTER-001` has a reserved contract surface.
- Compat pin and intelligence packages can cite stable maturity posture.

## Explicit non-claims

- `ATLAS_2_1_RELEASE_CERTIFIED = NO` (unchanged)
- Not `v2.2.0` released / tagged
- Not authentic estate PILOT evidence
- Not `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`

## References

- `docs/atlas-2.1/CHARTER.md` — maturity vocabulary source
- `docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md` — DAG first READY slot
- `docs/atlas-2.2/README.md` — landed PREP index (read-only)

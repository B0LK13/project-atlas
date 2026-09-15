# ADR-2.2-CONFLICT-UX-002 — Conflict UX deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-CONFLICT-UX-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `b431494dc8860f4f1db3f327c9ccf991699ccfc5` |
| Tree | `26a59cd76bd9df410912b4552ddd907f7a160588` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 conflict UX PREP landed cockpit / disposition stubs with auto-resolve,
UI-write, and authority-elevation negatives under
`docs/atlas-2.2/conflict-ux/`. Sibling wave-2 deepen packages (mem-gov,
research, DoD) carry an explicit **forbidden-action** schema plus
release-cert / PILOT / LLM authority negatives. Conflict UX had invariants and
disposition negatives but lacked that deepen package card and forbidden-action
vocabulary.

## Decision

1. Land deepen package card, forbidden-action schema, deepen fixture plan, and
   certification / PILOT / LLM negatives under `docs/atlas-2.2/conflict-ux/**`
   only.
2. Keep existing disposition / cockpit / card / queue schemas and base
   negatives at their current paths — **no relocation or dual ownership**.
3. Forbid `release_cert_stamp`, `pilot_invent`, and `llm_authority_stamp` in the
   deepen forbidden-action vocabulary (enum also documents auto-resolve /
   UI-write / authority-elevation peers without relocating disposition).
4. Require deepen negatives to carry
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.
5. Treat DEMO VERIFIED as **not** release or PILOT credit.
6. Do **not** mutate runtime `conflict_projections` or apps until unlock.

## Consequences

- Positive: conflict UX reaches wave-2 sibling artifact depth; clear
  fail-closed certification vocabulary for future implementers.
- Negative: no live cockpit until post-`v2.1.0` unlock; fixtures grant no
  gate credit.

## Non-decisions

- Exact Mission / Workspace panel layout
- Whether Ask Atlas 2 embeds cards vs deep-links
- Any change to Core ConflictType enums or `conflict_projections` emit

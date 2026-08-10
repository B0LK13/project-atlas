# ADR-2.2-INTEL-SLICE-001 — Intelligence slice deepen (PREP boundary)

| Field | Value |
|---|---|
| Status | **Accepted (PREP boundary)** |
| Package | AS-2.2-INTEL-SLICE-DEEPEN-PREP-001 |
| Date | 2026-08-10 |
| Tip | `2fe504914eadef7d453b773fa4d96e3bb4175f47` |
| Tree | `3d82fa7552280afd82d68f8313dde5bfdaa30d9d` |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Context

Wave-1 intel-slice PREP landed architecture sketches plus sample / negative
fixtures under `docs/atlas-2.2/intel-slice/` with hard invariants
(slice ≠ authority, composition ≠ mutation, no silent conflict resolve,
LLM ≠ authority). Sibling wave-2 deepen packages (conflict-ux, mem-gov,
research, compat-pin) carry an explicit **forbidden-action** schema plus
release-cert / PILOT / LLM authority negatives. Intel-slice had inv + neg
payloads but lacked that deepen package card and forbidden-action vocabulary.

## Decision

1. Land deepen package card, forbidden-action schema, deepen fixture plan, and
   certification / PILOT / LLM negatives under `docs/atlas-2.2/intel-slice/**`
   only.
2. Keep existing sample envelopes and base negatives at their current paths —
   **no relocation or dual ownership**.
3. Forbid `release_cert_stamp`, `pilot_invent`, and `llm_authority_stamp` in the
   deepen forbidden-action vocabulary (enum also documents authority-elevation /
   silent-conflict-resolve / canonical-write peers without relocating base
   negatives).
4. Require deepen negatives to carry
   `evidence_class=fixture-only`, `authentic_estate=false`,
   `release_certified=false`, `pilot_pass=false`, `canonical_writes=false`,
   `status=rejected_forbidden`.
5. Treat DEMO VERIFIED as **not** release or PILOT credit.
6. Do **not** mutate runtime Core / apps until unlock.

## Consequences

- Positive: intel-slice reaches wave-2 sibling artifact depth; clear
  fail-closed certification vocabulary for future implementers.
- Negative: no live intelligence-slice composer until post-`v2.1.0` unlock;
  fixtures grant no gate credit.

## Non-decisions

- Exact Ask / MCP / Estate-Ops lens layout for the composed envelope
- Whether incomplete slices block consumers or surface `unknown[]` only
- Any change to Core authority / conflict / KF emit paths

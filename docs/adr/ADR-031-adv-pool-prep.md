# ADR-031 — Atlas 2.2 ADV pool prep (threat matrix)

**Status:** accepted for documentation / PREP only  
**Date:** 2026-08-10  
**Work package:** AS-2.2-ADV-POOL-001  
**Baseline:** MAIN `80ab762` / TREE `cfc667a` (post-#173 tip)  
**Depends on:** ADR-004 (prompt-injection / quarantine), 2.1 ADV-LIVE-SUITE (read-only reference)

## Context

Atlas 2.1 landed Host/CORS, L3, and ops-receipt adversarial coverage
(`#154` / `#155`). Atlas 2.2 P1 prep surfaces (RET / CTX / MEM / KCI / DoD /
TIME / REALITY / RESEARCH) need a **shared threat catalog** before
implementation unlock, without reopening drained 2.1 ADV rows or mutating
runtime.

## Decision

1. Maintain an additive ADV matrix under `docs/atlas-2.2/adv-pool/` owned by
   **AS-2.2-ADV-POOL-001**.
2. Keep `docs/atlas-2.1/ADV-LIVE-SUITE.md` **read-only** for this package —
   do not rewrite landed ADV-2.1-01…22 rows.
3. Encode fail-closed, no-secret-leakage, and no-authority-elevation as
   cross-cutting invariants (ADV-2.2-X-*).
4. Defer executable suite promotion to a post-unlock 2.2 ADV package after
   `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED`.
5. Explicit flags: `ATLAS_2_1_RELEASE_CERTIFIED = NO`; no PILOT invent.

## Consequences

- Sibling 2.2 prep packages can cite ADV-2.2-* row IDs without dual-owning
  the 2.1 live suite.
- Presence tests may assert matrix coverage and forbidden reopen language
  without importing live API/MCP/L3 harnesses.
- No `src/` or web changes land under this ADR.

## Non-decisions

- Exact executable test module layout for post-unlock 2.2 ADV live suite
- Any change to 2.1 Host/CORS / L3 / ops-receipt behavior

# ADR-2.2-MEM-GOV-001 — Governed agent memory (PREP)

**Status:** proposed (prep only; non-normative until 2.2 unlock + schema freeze)  
**Date:** 2026-08-10  
**Work package:** AS-2.2-MEM-GOV-001 / AS-2.2-MEM-GOV-PREP-001  
**Branch:** `feat/as-2.2-mem-gov-prep`

## Context

Atlas agents need durable reminders and session-derived context. Existing
planes cover **agent-event receipts** (ingest + AS-INT-011 revocation) and
**fixture context packs** (AS-2.0-CTX-001), but not a first-class **governed
memory** record with provenance, revocation, expiry, and supersession.

Without an explicit contract, future 2.2 implementations risk:

- promoting LLM or agent prose into Layer B authority
- retrieving revoked or stale units as current
- dual-active forks for the same logical key
- colliding with receipt-revocation ownership (AS-INT-011)

Pre-`v2.1.0` policy allows docs / contracts / fixtures / ADRs only
(`docs/strategy/ATLAS-2.2-EXECUTABLE-ROADMAP.md`).

## Decision

1. Introduce prep-only contracts under `docs/atlas-2.2/contracts/mem-gov/` for
   governed agent memory records and the four governance axes.
2. Keep the memory plane **operational** with `authority_plane=none` and
   `consume_only=true`.
3. Require provenance on every record; fail closed without it (future impl).
4. Treat revocation, expiry (as-of evaluated), and supersession as first-class
   status transitions — not soft hints.
5. Do **not** ship package-data schemas or `src/` modules in this PREP.
6. Do **not** dual-own AS-INT-011 receipt revocation indexes.

## Consequences

- 2.2 implementers inherit a shared vocabulary before unlock.
- Merge risk stays in `docs/atlas-2.2/**` + one unique unit test — no 2.1
  runtime semantic mutation.
- Post-unlock work must freeze schemas, assign sole-writer module ownership,
  and schedule ADV/IV before claiming production readiness.
- Consumers (CTX compiler, Agent OS, Ask) may later read **active** memory
  pointers only; revoked/expired/superseded units stay non-authoritative.

## Non-decisions (explicitly deferred)

- Storage layout under `generated/ops/` vs control-plane spool
- Vector / embedding memory backends
- Cross-vault federation of memory
- Automatic promotion of memory into claims

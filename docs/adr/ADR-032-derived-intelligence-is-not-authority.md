# ADR-032 — Derived intelligence is not authority

**Status:** accepted for isolated Wave-1 implementation
**Date:** 2026-08-15
**Scope:** AS-2.0-INTEL-001, AS-2.0-INTEL-002, AS-2.0-STATE-001

## Context

Atlas already stores objective claim signals (authority, lifecycle,
provenance, valid-time) and already has compiler-written conflict and
current-state records. Wave 1 needs a machine-usable derived layer that
answers evidence quality, contradiction candidacy, and project-state
questions without becoming a second source of truth.

The `#357` → `#354` integration train is active. Shared Web, Roadmap,
CLI, and schema-catalog surfaces must not be touched.

## Decisions

1. Derived intelligence lives in a new `project_atlas.intelligence`
   package. It imports existing domain / temporal helpers and never
   writes claims, sources, Layer B, or vault files.
2. Confidence is a discrete class (`high` / `medium` / `low` /
   `unknown`) plus explainable limiting factors. No numeric value is
   presented as probability.
3. Contradiction candidates are not proven falsehoods and are never
   auto-resolved.
4. Derived project state uses OBSERVED / DERIVED / UNKNOWN / CONTESTED /
   STALE. It does not invent health or roadmap status.
5. Future HTTP and Web contracts are documentation-only in this wave.
   No route registration.

## Consequences

- `DERIVED_INTELLIGENCE_IS_AUTHORITY = NO` is a permanent invariant.
- UNKNOWN remains a valid honest result.
- Schema catalog / `schema.py` stay untouched (no migration).
- Merge authorization is not granted by this ADR.

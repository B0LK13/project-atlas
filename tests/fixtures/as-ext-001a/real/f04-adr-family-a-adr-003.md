# ADR-003 — Governed agent-event ingestion contract

**Status:** accepted for implementation  
**Date:** 2026-08-01  
**Work package:** AS-INT-001

## Context

Atlas Control Plane produces verified agent evidence while Atlas Core owns the
canonical OKF Vault. Direct imports or direct Markdown writes would couple the
subsystems and bypass Core's independent source trust boundary.

## Decision

Introduce the dependency-light `src/atlas_contracts/` package with versioned
typed records for event identity, skill/Vault binding, provenance, pipeline
state, receipts and event-package inventories. Control Plane packages are
discovered under `.atlas-inbox/agent-events/<project-id>/<event-id>/` and are
revalidated by Core before any canonical write.

Core stores accepted packages as source evidence, emits deterministic
project-local activity projections, and quarantines pending, malformed,
conflicting, hash-mismatched, wrong-Vault and unsafe packages. Control Plane
internals remain outside the shared package.

## Consequences

- The contract can evolve independently through explicit schema versions.
- Core can compile event evidence offline without invoking Control Plane code.
- Invalid event packages remain visible without becoming project truth.
- The first implementation uses maintained execution evidence; semantic
  ConceptRecord/Claim construction remains deferred.

# ADR-002 — Atlas two-track platform reconciliation

**Status:** accepted  
**Date:** 2026-08-01  
**Decision authority:** Project Atlas Program Reconciliation Directive

## Context

The repository contains two implementations using the Project Atlas name:
the `src/project_atlas/` OKF compiler and the `atlas-vault-documentation/`
governed-agent evidence pipeline. Treating them as competing products would
create duplicate ownership of the canonical Vault and unclear integration
boundaries.

## Decision

Project Atlas is one platform with three explicit streams:

1. **Atlas Core** — `src/project_atlas/`. It owns project/document discovery,
   inventory, ingestion, identity, normalization coordination, canonical OKF
   Vault compilation, indexes, navigation, validation, incremental rebuilds,
   providers, and context packs.
2. **Atlas Control Plane** — `atlas-vault-documentation/`. It owns governed
   agent bootstrap, skills, identities, sessions, event capture, offline
   spool, normalization/verification of agent events, receipts, concurrency,
   completion gates, and repository enforcement.
3. **Atlas Graph Layer** — future derived relationship functionality. It may
   consume source-linked records from Core and Control Plane but cannot become
   authoritative source evidence.

Atlas Core owns the canonical OKF Vault and final generated indexes. Atlas
Control Plane produces immutable, verified governed agent-event evidence; it
must not directly own or mutate Core's canonical project indexes, coverage
maps, global indexes, or final navigation structures. The integration boundary
is a governed agent-event source package consumed by Atlas Core ingestion.

## Consequences

- The two implementations remain separate and independently testable.
- A small versioned shared-contract package may define stable identities,
  provenance, receipts, Vault identity, ingestion state, and schema versions;
  implementation internals do not move into that package.
- The first integrated vertical slice is `discover → ingest → build-indexes →
  validate`, with Control Plane event packages treated as a supported source.
- AS-SKILL-001 and AS-CTRL-001 are certified. Atlas Core is not complete; its
  original discovery/ingestion/index/validation commands remain the primary
  next product path.

## Migration and validation

Existing paths are retained to avoid disruptive renames. Product terminology
and architecture documentation use the three-stream model. Future work
packages must declare their owning stream and must preserve the source-of-truth
hierarchy. The integrated acceptance fixture must prove deterministic event
ingestion, provenance, no-op replay, and zero canonical mutations on an
unchanged rerun.

## Alternatives rejected

- Blindly merging the two source trees would blur ownership and increase
  coupling.
- Continuing as two competing products would duplicate Vault and receipt
  semantics.
- Treating Graphify output as authoritative would violate the evidence
  hierarchy.

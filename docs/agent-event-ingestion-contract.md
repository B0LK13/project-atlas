# AS-INT-001 — Governed Agent-Event Ingestion Contract

**Status:** implementation complete — certification pending  
**Contract schema:** version 1  
**Owner:** Atlas Core integration boundary

## Boundary

Atlas Control Plane owns agent/session identity, skill binding, capture,
normalization, verification, receipts and spool state. Atlas Core owns source
discovery, ingestion, canonical OKF compilation, activity projections and
strict Vault validation. Core consumes event packages through
`atlas_contracts`; it does not import Control Plane internals.

```text
managed session
  → verified .atlas-inbox/agent-events package
  → atlas discover
  → atlas ingest
  → activity/session projections
  → atlas validate
```

## Package contract

Each package is rooted at:

```text
.atlas-inbox/agent-events/<project-id>/<event-id>/
├── event.md
├── event.json
├── provenance.json
└── receipt.yaml
```

`event.json` contains schema version, event identity/type, skill and Vault
binding, provenance hashes, complete pipeline state and receipt reference.
The package validator revalidates all four files at ingestion, recomputes
component hashes, checks the event/provenance/receipt bindings, requires all
pipeline stages to be true, and confines every path to the source root and
Vault root.

Event ingestion also requires `.atlas/vault.json` and
`.atlas/agent-event-policy.json` in the target Vault. The policy is
deployment-provisioned from the certified AS-SKILL-001 receipt and contains
the trusted skill ID, version and SHA-256. A syntactically valid but unknown
skill hash is quarantined; Core does not trust the package's self-assertion.

The shared typed models live in `src/atlas_contracts/`. JSON schemas under
`src/atlas_contracts/schemas/` are lockstep-tested with the models. Package
identity is never inferred from unvalidated path text.

## Authority and quarantine

Verified packages are maintained execution evidence. Completion and validation
events remain derived evidence and cannot silently override primary project
documentation. Pending, malformed, hash-mismatched, wrong-Vault, traversal and
conflicting packages remain visible in `quarantine/agent-events/index.json`
and are excluded from canonical activity projections.

## Core projections and state

Accepted packages are copied as source evidence beneath:

```text
sources/agent-events/<project-id>/<event-id>/
receipts/agent-events/<project-id>/<event-id>.yaml
state/agent-events/<project-id>.json
```

Core generates deterministic project-local `activity.md`, `sessions.md`,
`validations.md`, `decisions.md`, `blockers.md`, and `work-packages.md`.
Every entry links to its event package. Repeated ingestion of unchanged
packages is compare-before-write and produces no duplicate activity entries.

## Public workflow

```bash
atlas discover --source <project-root> --output <manifest.json>
atlas ingest --manifest <manifest.json> --vault <vault> --source <project-root>
atlas build-indexes --vault <vault>
atlas validate --vault <vault>
```

## Deferred scope

Cross-project identity, Control Plane inbox production changes, semantic
ConceptRecord construction, content secret scanning, and Graph Layer behavior
remain separate work packages.

Integration follow-up items cover skill-policy rotation/revocation,
removed-package state, schema migration and the bounded multi-project
pilot. Raw-package and receipt retention is defined by AS-INT-009
(`docs/AS-INT-009-retention-policy.md`). Removed-package tombstones are
AS-INT-010 (`event_tombstones`). Receipt revocation / invalidation is
AS-INT-011 (`docs/AS-INT-011-receipt-revocation.md`).

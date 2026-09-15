# Implementation Roadmap

## Phase 0 — Skill contract

Deliver the skill, governing standard, event taxonomy, schema, path mapping, adapters, and sample event.

Exit gate:

- documents are internally consistent;
- mda-cli can resolve the directory;
- sample input has a deterministic expected normalized structure.

## Phase 1 — Deterministic capture

Deliver:

- atomic raw-event writer;
- stable event IDs;
- secret redaction;
- vault/spool fallback;
- configuration discovery;
- JSON output.

Exit gate:

- capture works offline;
- duplicate explicit IDs never overwrite;
- writes cannot escape roots.

## Phase 2 — Documentation validation

Deliver:

- raw-event validator;
- spool detector;
- metadata and taxonomy checks;
- secret validation;
- receipt validation.

Exit gate:

- clean fixtures pass;
- malformed and secret-bearing fixtures fail;
- strict pending spool returns non-zero.

## Phase 3 — mda-cli normalization

Deliver:

- normalization command builder;
- output discovery and validation;
- provider failure capture;
- immutable-source enforcement.

Exit gate:

- raw events remain unchanged;
- output has source provenance;
- provider failure remains visible.

## Phase 4 — Atlas router

Deliver:

- idempotent project log append;
- normalized event placement;
- work-package update;
- conditional concept proposals;
- human-safe generated-region updates;
- partial-routing receipts.

Exit gate:

- rerouting does not duplicate;
- malformed human markers fail closed;
- all links resolve.

## Phase 5 — Agent hooks

Deliver:

- repository startup hook;
- phase capture hooks where supported;
- end-of-task receipt gate;
- multi-agent coordination;
- CI documentation check.

Exit gate:

- representative agents use one transaction contract;
- missing receipts or pending strict spool fail the gate.

## Phase 6 — Atlas native integration

Deliver:

```text
atlas capture
atlas normalize
atlas route
atlas docs-check
```

Add event impact graphs and a portfolio activity feed.

Exit gate:

- helper scripts become thin Atlas CLI clients;
- events are traceable from raw source to portfolio view.

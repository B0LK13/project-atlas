# Atlas 2.0 — Schema / API drafts (PREP · non-shipping)

Status: **PREP ONLY**. Draft shapes for review. **No** JSON Schema files under
`src/project_atlas/schemas/` for 2.0. `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Rules

- Drafts are documentation sketches only (YAML/Markdown tables).
- Freeze requires §98 checklist + owner auth + 1.0 RELEASE CERTIFIED.
- 1.0 wins dependency conflicts.

## Draft envelopes (names reserved)

| Draft ID | Consumer | Notes |
|---|---|---|
| `atlas.2.0.federation-join-request.v0` | FED-001 | members[], identity pins, operator auth ref |
| `atlas.2.0.command-center-read-model.v0` | UX-001 | source pin, freshness, non-authority labels |
| `atlas.2.0.provider-adapter-result.v0` | PROV-001 | quarantine required until provenance pass |
| `atlas.2.0.sync-plan-v2.v0` | SYNC-001 | extends 1.0 dry-run scaffolds; estate gated |
| `atlas.2.0.compat-snapshot-consumer.v0` | COMPAT-001 | requires certified 1.0 HEAD/TREE/tag |
| `atlas.2.0.kci-query.v0` | KCI | read-only; explain/diagnose sidecars |
| `atlas.2.0.context-pack.v0` | CONTEXT | provenance pointers mandatory |
| `atlas.2.0.agent-os-session.v0` | AGENT-OS | receipt-gated lifecycle |

## Explicit

Shipping these as package data before freeze is **FORBIDDEN**.

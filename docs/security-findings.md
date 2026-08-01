# Atlas Core Security Findings

## AT-013 — manifest-controlled path traversal

**Status:** remediated on `feat/atlas-core-vertical-slice`; independent replay
required before merge.

Before the fix, `atlas ingest` trusted the raw `likely_project` value from a
hand-crafted `source-manifest.json`. The public command boundary accepted:

```json
{"likely_project":"../../../../outside-vault-marker"}
```

and wrote `project.md` and `documentation-map.md` outside the configured Vault
root. The original reproduction and post-fix evidence are preserved in
`docs/evidence/atlas-core-ingestion-traversal.json`.

The remediation validates every manifest source through `SourceRecord`, rejects
unsafe project and source identifiers, preflights all eligible records before
writes, and confines every derived destination beneath the resolved Vault
root. The rejected transaction preserves the previous valid Vault byte-for-byte.

### Residual security scope

The controlled slice does not yet perform content-based secret detection.
Filename-only sensitive-file detection remains explicit but is not sufficient
for the real-project pilot. See backlog item `CORE-SEC-001`.

## AS-INT-001 integration controls

The event-package boundary applies the AT-013 root-confinement posture to
project IDs, event IDs, package components, Vault destinations and receipt
paths. Hash mismatches, wrong Vault identity, pending/unverified pipeline state,
malformed packages and conflicting event IDs are quarantined before canonical
activity projections. Independent certification of the integration package is
still required.

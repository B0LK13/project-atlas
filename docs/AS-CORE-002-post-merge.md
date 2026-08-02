# AS-CORE-002 Post-Merge Certification Report

## 1. Decision

`AS-CORE-002 CERTIFIED`

The semantic domain model, source lifecycle behavior, secret exclusion,
human-safe regeneration, and transaction preflight are merged into `main`.
The controlled merge commit is `50509a21e30a965a9b0e2e10cdaf72ed24d135cb`.
The implementation, remediation and transaction-preflight commits remain
individual ancestors; no squash was used.

## 2. Scope and transaction boundary

Commit `f970e72` stages all canonical ingestion outputs in an in-memory
`write_plan` and promotes them only after all affected projects have passed
generated-marker validation and all records have rendered successfully. The
plan covers imported source-document copies, event-package and event-receipt
copies, project pages, documentation maps, lifecycle and event state,
manifests, reports, quarantine output and event projections.

The two-project regression has `aaa-first` receive a newly added `NOTES.md`
while `zzz-second` has a malformed generated marker. The failed invocation
produces zero Vault mutations. After the marker is corrected, retry imports
`NOTES.md` exactly once, updates lifecycle state once, and completes without
duplicates.

## 3. Reconciled validation evidence

All commands below were run from merged `main` at `50509a2`:

| Gate | Result |
|---|---|
| Full repository suite | `./.venv/bin/python -m pytest -q` — **88 passed** |
| Documentation/control-plane suite | `./.venv/bin/python -m pytest atlas-vault-documentation/tests -q` — passed |
| AS-CORE-002 focused suite | schema, semantic model, lifecycle, security and transaction tests — **25 passed** |
| Mypy | `./.venv/bin/python -m mypy src atlas-vault-documentation` — no issues in 127 source files |
| Ruff | `./.venv/bin/python -m ruff check .` — passed |
| Compilation | `./.venv/bin/python -m compileall -q src atlas-vault-documentation` — passed |
| Public CLI workflow | `init → discover → ingest → build-indexes → validate` — passed |
| Strict Vault validation | 39 Markdown files validated — passed |
| Unchanged replay | canonical SHA-256 manifest identical; zero content changes — passed |

The prior AS-CORE-002 receipt reported 87 for the full repository suite; the
exact post-merge result is 88 passed and is the corrected undercount.

## 4. Independent behavior checks

The merged tests and post-merge probes confirm:

- invalid nested semantic records are rejected by JSON Schema;
- corrupt lifecycle state is rejected before writes;
- supported lifecycle values remain compatible;
- malformed markers fail closed without changing the prior Vault;
- corrected retry succeeds once with no duplicate import;
- content-based secret findings exclude secret-bearing sources and emit only
  redacted metadata;
- protected human regions survive regeneration;
- public CLI validation passes;
- unchanged replay performs no canonical changes.

## 5. Control Plane and ancestry reconciliation

The merge diff contains only AS-CORE-002 files plus its backlog and roadmap
status updates. No Control Plane implementation paths were introduced.
Commits `575ce3b`, `bb2a713`, `4ea9bd7` and `f970e72` are ancestors of the
validated merge.

## 6. Deferred items

The following remain explicitly deferred:

- richer Claim and Concept population;
- schema/Pydantic coercion edge cases;
- generated-marker convention reconciliation;
- state-migration tooling;
- real-project pilot certification.

These deferrals do not invalidate the bounded AS-CORE-002 certification.

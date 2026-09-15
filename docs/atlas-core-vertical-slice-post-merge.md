# Atlas Core Vertical Slice — Post-Merge Milestone

**Status:** passed  
**Merge commit:** `32243d0` (`merge: complete Atlas Core vertical slice`)  
**Branch:** `main`  
**Baseline:** `672cd4e` / `atlas-reconciliation-baseline-2026-08-01`  
**Feature boundary:** `feat/atlas-core-vertical-slice`

## Commit range

The non-fast-forward merge preserves the implementation and remediation
boundaries:

```text
2cc2091 feat: add Atlas Core discovery ingestion vertical slice
60ba270 docs: record Atlas Core vertical slice receipt
d523220 fix: confine Atlas Core ingestion to Vault root
b25cdb1 docs: finalize Atlas Core remediation evidence
32243d0 merge: complete Atlas Core vertical slice
```

The AT-013 remediation and its evidence remain separate commits; they were not
squashed into the original feature commit.

## Post-merge validation

| Gate | Result |
|---|---|
| `./.venv/bin/python -m pytest -q` | 65 passed |
| `./.venv/bin/python -m mypy src atlas-vault-documentation` | 117 source files, no issues |
| `./.venv/bin/python -m ruff check .` | passed |
| `./.venv/bin/python -m compileall -q src atlas-vault-documentation` | passed |
| AT-013 regression | 8 passed |
| Controlled CLI workflow | 13 sources ingested; 42 Markdown files validated |
| Malicious manifest CLI probe | rejected; 0 escaped destinations |
| Unchanged replay | content drift 0; canonical changes 0; filesystem writes 0 |
| Independent verification worktree | unchanged at `d523220`; clean |

The workflow exercised:

```text
atlas discover → atlas init → atlas ingest → atlas build-indexes → atlas validate
```

The second ingest/index/validate pass produced byte-identical content and
unchanged file metadata.

## Acceptance and security status

The bounded vertical slice provides the user-visible `discover`, `ingest`,
`build-indexes`, and `validate` commands, deterministic source identity and
ordering, source SHA-256 provenance, explicit unsupported/sensitive records,
deterministic indexes, and structural/link validation.

AT-013 is remediated and independently verified. Ingestion revalidates every
manifest record through `SourceRecord` and confines every derived destination
to the resolved Vault root. The original exploit and independent verification
remain recorded in `docs/evidence/atlas-core-ingestion-traversal.json`.

## Deferred work

- `CORE-MODEL-001`: formal `ConceptRecord`/`Claim`/`ProvenanceReference`
  construction and richer project frontmatter.
- `CORE-SEC-001`: content-based secret detection and redaction before real
  project ingestion.
- `CORE-OPS-001`: continued explicit filesystem-write accounting for no-op
  replay.
- Full discovery/classification/coverage/conflict/deletion backlog.
- Atlas Control Plane governed agent-event inbox integration.

## Next authorized package

The next bounded package is the shared agent-event ingestion contract and the
first Atlas Core integration with verified Atlas Control Plane event packages.
No broad real-project ingestion or Graph Layer implementation begins as part
of this milestone.

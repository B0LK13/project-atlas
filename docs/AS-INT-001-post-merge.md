# AS-INT-001 — Post-Merge Validation and Certification

**Status:** AS-INT-001 CERTIFIED  
**Merge commit:** `0daa7c7` (`merge: integrate governed agent-event ingestion`)  
**Feature head:** `efeb5f9`  
**Validated branch:** `main`  
**Core milestone:** `atlas-core-vertical-slice-v1`

## Disposition

The governed agent-event ingestion contract was merged into `main` with a
non-fast-forward merge. The merged result preserves the Atlas Core and Atlas
Control Plane ownership boundary: Core consumes validated event packages via
`src/atlas_contracts/`; it does not import Control Plane internals, and no
Control Plane certification files were changed by the integration branch.

## Contract and workflow

The version-1 package contains `event.md`, `event.json`, `provenance.json`,
and `receipt.yaml` under the validated `.atlas-inbox/agent-events/<project>/<event>`
layout. Core revalidates the package at ingestion, checks hashes, identity,
Vault binding, skill policy, pipeline state, provenance and receipt linkage.

The public workflow is:

```text
atlas discover → atlas ingest → atlas build-indexes → atlas validate
```

The controlled fixture produces activity, session, validation, decision,
blocker and work-package projections, with links back to source packages and
receipts. Pending, malformed, traversal, conflicting, wrong-Vault,
skill-mismatch and symlinked packages remain explicit quarantine evidence.

## Independent verification

Agent Two independently reproduced the implementation evidence and reported
`AS-INT-001 MERGE RECOMMENDED`. The exact independent results were 12 focused
tests, 77 Core tests, 146 Control Plane tests, 124 mypy source files, clean
Ruff and compilation. Fresh adversarial probes confirmed:

- a symlinked package is isolated and quarantined while legitimate sources
  continue through discovery and ingestion;
- a trusted skill hash is accepted;
- a mismatched skill hash is rejected;
- a missing trusted skill policy is rejected;
- traversal, duplicate, replay and provenance protections remain effective.

This is distinguished from the implementation agent's self-reported evidence;
the independent review is now complete and is recorded in the integration
receipt.

## Historical defects retained

The earlier review findings remain visible rather than being erased:

1. A symlinked package initially escaped the isolated quarantine path and
   aborted discovery. The refinement exception was corrected in `efeb5f9`.
2. A syntactically valid but untrusted skill hash initially passed package
   validation. Trusted Vault skill policy enforcement was corrected in
   `efeb5f9`.

Both defects were independently reproduced and re-tested after remediation.

## Merged-main validation

Exact commands and observed results:

| Check | Result |
|---|---|
| `./.venv/bin/python -m pytest -q` | 77 passed |
| `./.venv/bin/python -m pytest atlas-vault-documentation/tests -q` | 146 passed |
| `./.venv/bin/python -m pytest tests/unit/test_atlas_contracts.py tests/integration/test_agent_event_ingestion.py -q` | 12 passed |
| `./.venv/bin/python -m mypy src atlas-vault-documentation` | no issues in 124 source files |
| `./.venv/bin/python -m ruff check .` | passed |
| `./.venv/bin/python -m compileall -q src atlas-vault-documentation` | passed |

The focused public-boundary tests cover valid event-package ingestion,
projection generation, symlink quarantine, trusted and mismatched skill
policies, missing policy, wrong Vault identity, conflicting IDs, identical
replay, and no-op write accounting. Structural and internal-link validation
passed in the workflow.

Replay evidence distinguishes content and filesystem behavior: unchanged
event-package replay produced zero content drift, zero canonical changes, zero
filesystem writes, and zero duplicate activity entries.

## Residual and deferred scope

The following remain explicitly outside this certified package: automatic live
Control Plane inbox production changes, full semantic `ConceptRecord`/`Claim`
construction, content-based secret scanning (`CORE-SEC-001`), cross-project
identity, and Atlas Graph Layer behavior. Retention, deletion state, receipt
revocation, schema migration and the bounded multi-project pilot remain tracked
integration follow-up work.

## Certification

The post-merge receipt is
`docs/evidence/AS-INT-001-post-merge-receipt.yaml`. The updated work-package
receipt is `docs/evidence/AS-INT-001-receipt.yaml`. The final annotated tag
`atlas-agent-event-integration-v1` is created only after the evidence commit
containing these records is validated.

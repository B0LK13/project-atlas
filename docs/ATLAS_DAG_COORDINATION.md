# ATLAS DAG Coordination (`atlas-dag`)

Read-only autonomous DAG coordinator for Windows Main. Implements directives
D-002 (GitHub event bus), D-006 (`atlas-dag` CLI), D-007 (`ATLAS_IV_RECEIPT_V1`),
and D-008 (read-only Merge Guardian). MVP prohibitions hold: **no automatic merge,
no product runtime changes.**

## Components

- `schemas/atlas_event_v1.schema.json` — append-only transition events.
- `schemas/atlas_iv_receipt_v1.schema.json` — exact-head formal IV receipts.
- `schemas/atlas_evidence_v1.schema.json` — conservative evidence cache records.
- `schemas/dag_snapshot_v1.schema.json` — disposable snapshot shape.
- `scripts/atlas-dag.py` + `scripts/atlas_dag/` — the CLI and its modules.
- Runtime state: `.atlas-runtime/dag.json` and `.atlas-runtime/evidence/`
  (gitignored, disposable).

## Event bus (D-002)

One GitHub issue named `Atlas Autonomous DAG Control`. Events are fenced
` ```json ` blocks inside append-only comments. Rules:

1. Repository/GitHub truth overrides comments.
2. Only `ATLAS_EVENT_V1` transitions; stable-state noise (`NO_CHANGE`,
   `HEAD_UNCHANGED`, `CI_STILL_RUNNING`, `STILL_WAITING`, `STILL_FROZEN`) is rejected.
3. Duplicate `event_id` is idempotent; events are canonically ordered by
   `(timestamp_utc, event_id)`, so reordering cannot change reconstruction.
4. A verifier pool is declared in the issue body as an
   `ATLAS_VERIFIER_POOL_V1` fenced block. Entries bind a verifier to a trusted
   principal — the GitHub login that may actually author receipts:

   ```json
   {"schema": "ATLAS_VERIFIER_POOL_V1", "verifiers": [
     {"verifier_id": "IV-A", "principal": "github:some-login"},
     {"verifier_id": "IV-B", "principal": "github:other-login"}
   ]}
   ```

   Bare-string entries remain parseable as `DECLARED_BUT_UNBOUND` but never
   satisfy formal IV. No pool, no binding, or a receipt comment authored by a
   different login => fail-closed (`VERIFIER_POOL_UNDEFINED`,
   `VERIFIER_IDENTITY_UNBOUND`, `PRINCIPAL_MISMATCH`).

5. The event bus is append-only; `gh api --paginate` consumes every comment
   page. Stale-head events (their `head` differs from the live PR head) are
   history only and never affect current claim/freeze/ownership state.

## CLI

```bash
python scripts/atlas-dag.py --repo B0LK13/project-atlas snapshot   # writes .atlas-runtime/dag.json
python scripts/atlas-dag.py frontier
python scripts/atlas-dag.py inspect 709
python scripts/atlas-dag.py events
python scripts/atlas-dag.py owners
python scripts/atlas-dag.py gate 709    # exit 0 = PASS, 1 = FAIL, 2 = unknown PR
python scripts/atlas-dag.py evidence-ingest ev.json   # validate + store ATLAS_EVIDENCE_V1
python scripts/atlas-dag.py evidence 709              # reuse classification vs live head/tree
```

Fail-closed: unavailable GitHub data => `UNKNOWN`; ownership ambiguity =>
`AMBIGUOUS` (never last-writer-wins, never write authorization).

## Conservative evidence cache (D-009)

Append-only store at `.atlas-runtime/evidence/` of `ATLAS_EVIDENCE_V1` records
(producer, PR, head/tree at production, environment, covered files, covered
semantic contract, result, negative control, scope, created_at_utc). Ingestion
is schema-validated and idempotent on `evidence_id`; writes are atomic
(temp + `os.replace`) and byte-deterministic. The cache **classifies** reuse —
it never feeds the D-008 gate and never weakens exact-head certification.

Reuse classes:

- `EXACT_HEAD_ONLY` — record's head AND tree match the live candidate exactly.
- `REUSABLE_SUBSYSTEM` — subsystem-scoped record reused after a head move ONLY
  with an explicit equivalence proof for its covered contract (a callable or a
  record attesting semantic equivalence between old and new candidate).
  Absence of file overlap is never proof by itself.
- `PREDECESSOR_SUPPORTING` — retained as history/supporting context after
  invalidation; never certification.
- `INVALID` — malformed record (missing/unknown fields), failed negative
  control, or unverifiable provenance.

Never-weakening rule: after ANY head movement, candidate-wide exact-head CI,
whole-candidate formal IV, and whole-candidate native certification are NEVER
reusable as certification — they demote to `PREDECESSOR_SUPPORTING`. Subsystem
evidence without an explicit equivalence proof demotes the same way. Unknown
live head/tree (GitHub unavailable) classifies as `UNKNOWN` — fail closed, never
invented.

## Merge Guardian identity invariant (D-008)

`REMOTE PR HEAD = CI HEAD = IV HEAD = MERGE CANDIDATE HEAD`.

An open PR's prospective `merge_commit_sha` is never an actual merge receipt; a
`MERGED`/`SEALED` event while the PR is open fails the gate with
`MERGE_RECEIPT_UNPROVEN`. Head movement demotes prior exact-head CI and
whole-candidate IV to predecessor evidence.

## Tests

`tests/unit/test_atlas_dag.py` — offline adversarial suite (fake `gh` runner)
covering the acceptance matrix: DAG-001…005, OWN-001/002, IV-001…004,
CI-001…003, MG-001, EV-001…003, plus snapshot determinism and schema conformance.

# ATLAS-LIVE-COMPONENT-INTEGRATION-002 — delivery

## Flags (separate)

| Flag | Value |
| --- | --- |
| `COMPONENTS_AVAILABLE` | **YES** |
| `LIVE_INTERFACES_CONNECTED` | **YES** (TaskContract ↔ context ↔ readiness via public models + explicit bridge) |
| `CONTROLLED_CHAIN_PASSED` | **YES** (INT-013 EXTERNAL_BLOCKED preserved + LCI-002-TEST-OWNED chain) |
| `INDEPENDENT_REVIEW` | **NO** |
| `REAL_LAUNCH_AUTHORIZED` | **NO** |

A positive score on the first three does **not** grant the last two.

## Component identities (from artifacts, not truncated chat)

| Component | Role tested | HEAD | TREE |
| --- | --- | --- | --- |
| Taskcontract | tip = impl | `b0c35270494890cd9acd067c4a02e70fd0503cf7` | `f195eeb8aecf6af5b5d47ef59bfadb4dc4b51dcf` |
| Context impl | feature | `94e7b397e9d2400643228f50468be624504e20bd` | `cb81c8f072607a1503aedf1be6cd5d2f8cf59077` |
| Context tip | impl + docs pin | `0a2541b5cc18bd16cbc61ec5c6eba1ffb2cb257d` | `9811bd84c20c3bafa8c65737dde24099d1574c5b` |
| Readiness impl | feature | `a6746c2bdabbdb2c58ef60ffced589694433eae6` | `f6eb52e14a9f452389f6136f9d7d1848055df0d6` |
| Readiness tip | impl + docs pins | `bf98963766f873349ddb46f2fc7dfc4daee3b8f0` | `81ae18a437190706f6b4738cc8dac19dede2d3a2` |
| Supervisor base | PR #797 | `80280bfe13c77708cada7af17215acdaff3725e4` | (unchanged) |

Taskcontract bundle verified: SHA-256
`d75c08af67e96836df2c37bae31ed238e19e290524ee479ce135b2f8e8304ee7`
(`atlas-taskcontract-b0c35270.bundle`).

**What was tested on this candidate:** full tips of all three components composed
onto the taskcontract/#797 base (context + readiness tip trees checked out;
CLI registrations merged). Tip includes docs pins; implementation digests above
identify the code commits.

## Supervisor base decision

Integration candidate base = taskcontract tip (`b0c35270`), which already
includes `orchestration.program` from PR #797. Merge of #797 to main remains
an **owner decision** and is not claimed here.

## Isolated environment

| | |
| --- | --- |
| Worktree | `/home/gebruiker/Projects/project-atlas-worktrees/live-component-integration-002` |
| Branch | `feat/live-component-integration-002` |
| Venv | `/home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/venv` |
| Interpreter | that venv’s `bin/python` only (editable install of this worktree) |

Do not use foreign `PYTHONPATH` or another checkout’s `atlas` executable.

## Interface compatibility / translation layer

Module: `project_atlas.orchestration.live_integration`

| Direction | Mapping |
| --- | --- |
| TaskContract → context | `live_contract_to_context_snapshot` → `ContractSnapshot` (`source_kind=LIVE_MODULE`) |
| TaskContract → readiness | `live_contract_to_readiness_view` → `ContractView` |
| Context → handoff | packet `packet_id` + `content_digest` + freshness into `ReviewPackage` |
| Readiness → review | selection reasons, blockers, source revisions, optional `handoff_id` |

Production live load (`load_live_task_contract`) **fails closed** on schema
mismatch (`SCHEMA_INCOMPATIBLE`) — no silent fixture fallback.
`try_load_live_taskcontract` returns `None` for non-TaskContract files so
labeled fixtures still work in component tests.

## Reproduce demo (one command)

```bash
WT=/home/gebruiker/Projects/project-atlas-worktrees/live-component-integration-002
PY=/home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/venv/bin/python
$PY -m project_atlas.cli live-integrate demo \
  --int013-contract $WT/docs/orchestration/taskcontract/demo/contract.v1.json \
  --owned-contract $WT/tests/fixtures/live_integration/LCI-002-TEST-OWNED.contract.json \
  --workspace $WT/tests/fixtures/task-context-continuity/repo \
  --out /home/gebruiker/Projects/project-atlas-runs/live-component-integration-002/demo-report.json
```

## Tests on this candidate

```bash
$PY -m pytest \
  tests/unit/test_live_component_integration_002.py \
  tests/unit/orchestration/test_work_readiness.py \
  tests/unit/test_task_context_continuity_001.py \
  tests/unit/test_taskcontract_preparation.py \
  tests/unit/test_taskcontract_authority_and_evidence.py \
  -q --override-ini='addopts='
```

Recorded: **72 passed** (see `…/runs/live-component-integration-002/component-tests.txt`).

## Proven boundaries / remaining blockers

* INT-013 valid contract/program path does **not** clear `EXTERNAL_BLOCKED` /
  does not become `OFFERABLE_TO_DISPATCHER` without live runtime+auth.
* Positive path uses **test-owned** `LCI-002-TEST-OWNED` only.
* Live ClaimPort / EnrollmentPort / ResultPort production wiring still open
  (demo enrollment is test-labeled).
* Atomic claim-before-dispatch remains supervisor-owned.
* No push, merge, self-IV, real backlog launch, or #726 package mutation.

## Owner handoffs

| Owner | Handoff |
| --- | --- |
| Program / #797 | Decide main merge of supervisor base; wire live enrollment/claim ports |
| Task-contract | Keep `TaskContract` schema stable; consume bridge as optional client |
| Task-context | Prefer live TaskContract via `try_load_live_taskcontract`; fixtures labeled |
| Work-readiness | Consume `LiveContractPort` / bridge instead of fixture-only demos |
| Quality-loop | Provide live `ResultPort` when available |
| Independent reviewer | Review this candidate; local tests ≠ IV |
| Launch authority | Owner-gated; this package never authorizes |

## Integration HEAD/TREE

Filled after commit on `feat/live-component-integration-002`.

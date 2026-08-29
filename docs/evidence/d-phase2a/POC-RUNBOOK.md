# D-PHASE2A POC Runbook — Specification-Backed Autonomous Work Origination

Operator-grade instructions to reproduce the origination proof of concept
from clean state. See `docs/adr/ADR-033-phase2a-specification-backed-work-origination.md`
for the architecture decision this implements.

## Prerequisites

- This repository checked out at the exact commit this runbook ships
  with (see `git log -1` on the branch this file lives on).
- Python environment with `project-atlas` installed editable
  (`pip install -e ".[dev]"`) — this repo's own `.venv` already has this.
- `git` available on `PATH`.
- A **real project with pre-existing specification evidence**: a working
  tree containing `docs/ROADMAP.md` with a `## Roadmap record` fenced
  JSON block (schema `atlas.project-roadmap.v1`, same format
  `project_atlas.project_roadmap._parse_fenced_record` already parses),
  where at least one item has `status: NOT_STARTED` (or `IN_PROGRESS`),
  `lifecycle: READY`, and an `evidence` list including a test file
  carrying a module-level `pytestmark = pytest.mark.skip(...)` or
  `.xfail(...)`. This runbook's own worked example uses the real
  Gamma/TASK-017 estate — see "Estate identity" below.
- A **separate, already-implemented worktree** of that same project (or
  one you build per "Implementing the work" below) to serve as the
  `--execution-worktree` — Process B runs the real test suite there.

## Estate identity (this runbook's worked example)

This POC's worked example uses the `atlas-showcase-gamma` project from
the external `ATLAS-DEMO-ESTATE-001` demo estate
(`/mnt/d/Atlas-Demo/estates/atlas-showcase-gamma` on the machine this
POC was built on — a Windows-host path, not part of this repository).
Two git tags in that project's own history matter here:

- `atlas-demo-v1` — the frozen, certified baseline. **Never mutated by
  this POC.**
- `atlas-demo-v1-gamma-roadmap-successor` (commit `5a6436b2915d42d4355ff041c624564ab385eb44`)
  — an already-existing, independently-accepted successor revision (see
  that estate's own `manifests/gamma-roadmap-successor.json` and
  `manifests/gamma-roadmap-successor-independent-acceptance.json`) that
  adds the structured `## Roadmap record` block this POC's adapter
  reads. This POC did not create that revision; it reuses it as the
  origination source, per its own prior authorization.

`ORIGINATION_SOURCE` = a read-only `git archive` extraction of the
`atlas-demo-v1-gamma-roadmap-successor` tag (unimplemented TASK-017 —
this is the "before" state a real origination scan should see).

`EXECUTION_WORKTREE` = a `git worktree add` off the same tag, on a new
throwaway branch, with the real TASK-017 implementation committed on
top (this runbook's "Implementing the work" section below is exactly
how that worktree was built).

Neither operation touches the live `estates/atlas-showcase-gamma`
checkout or either tag — both are read-only references throughout.

## Reset / clean commands

```bash
# Origination source: a clean, read-only extraction (never a live checkout).
rm -rf /tmp/phase2a-origination-source
mkdir -p /tmp/phase2a-origination-source
git -C /path/to/atlas-showcase-gamma archive atlas-demo-v1-gamma-roadmap-successor \
  | tar -x -C /tmp/phase2a-origination-source

# Execution worktree: isolated, on a throwaway branch, never the tag itself.
git -C /path/to/atlas-showcase-gamma worktree add \
  /tmp/phase2a-execution-worktree atlas-demo-v1-gamma-roadmap-successor \
  -b phase2a-demo-execution

# Demo state (loop/lease/origination projections + throwaway identity repo).
rm -rf /tmp/phase2a-demo
```

## Implementing the work (one-time, real, spec-bound — not part of the
demo script itself)

The demo script (`run_three_process_demo.py`) does **not** write any
implementation code — Process B's "execution" step is real IN_PROCESS
execution *of already-completed work*, exactly matching how
`ExecutionHostClass.IN_PROCESS` is defined ("this package executes it
in-process"): the acting orchestrator process performs the bounded,
fully-specified implementation directly, as a distinct prior step, then
the demo proves recovery + real verification of that work.

To reproduce the implementation itself in `EXECUTION_WORKTREE`:
implement TASK-017 exactly per `docs/REQUIREMENTS.md` §3 and
`docs/adr/ADR-0002-task-017-dependency-validation.md` in that project
(4 new error classes, dependency validation on create/update, a
dependency-satisfaction precondition on `todo -> in_progress`,
dependency-aware worker readiness selection), remove the
`pytestmark = pytest.mark.skip(...)` line from
`tests/test_task_017_dependency_validation.py` (and only that line),
and commit. Full suite must be 93 passed, 0 skipped, 0 failed
(`PYTHONPATH=src python3 -m pytest tests/ -q`). One frozen-spec-test
fixture discrepancy was found and documented in that project's own
`docs/REQUIREMENTS.md` §3.4 during this process — see that file for the
exact, minimal, explicitly-justified one-line fix applied.

## Process A command

```bash
cd /path/to/project-atlas   # this repository, on this POC's branch
.venv/bin/python docs/evidence/d-phase2a/run_three_process_demo.py \
  --demo-root /tmp/phase2a-demo \
  --origination-source /tmp/phase2a-origination-source \
  --execution-worktree /tmp/phase2a-execution-worktree \
  --project-id atlas-showcase-gamma
```

This single invocation runs all three processes in sequence (each a
genuinely separate `python -c` subprocess sharing nothing but
`--demo-root`'s filesystem). To rehearse Process A alone, kill the
script after its first receipt line prints and re-run later — the
durable state under `--demo-root` is exactly what a real crash-and-resume
would leave behind.

## Expected Process A checkpoints

- stdout line: `Process A: ORIGINATED_AND_LEASED -- ORIG-<16-hex> ('<title>')`
- `--demo-root/receipts/process-a-receipt.json` exists with
  `"execution_ready": true`, `"risk_class":
  "O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION"`, `"owner_gate": null`.
- `--demo-root/origination/origination.json` exists and contains one
  record with `"state": "MATERIALIZED"`.
- `--demo-root/leases/leases.json` exists with one `"status": "ACTIVE"` row.
- `--demo-root/loop/state.json` (or wherever `loop.py`'s `CURRENT_NAME`
  resolves under `--demo-root/loop`) has `"phase": "LEASED"`.

## Process termination step

None needed manually — the script's own subprocess boundary between A
and B already is the "process terminates" event; each `python -c`
invocation is a real, separate OS process that exits normally after
printing its JSON receipt line, before the next one starts.

To rehearse this as an operator manually (rather than via the all-in-one
script), copy Process A's inline script out of
`run_three_process_demo.py` (the `process_a = f"""..."""` block, with
its `{...}` placeholders filled in), run it as its own `python -c` or
saved `.py` file, confirm it exits 0, and only then move to Process B.

## Process B command

Run as part of the same script invocation above, or manually per the
prior section using the `process_b` block.

## Expected Process B checkpoints

- stdout line: `Process B: RECOVERED_EXECUTED_VERIFIED_COMPLETED -- pytest '<N> passed in <t>s' -> final_node_state=CERTIFIED`
- `process-b-receipt.json`: `"rehydrated_from_disk": true`,
  `"verification_method": "real pytest subprocess against lease.worktree"`,
  `"pytest_returncode": 0`, `"verification_passed": true`,
  `"implementer_equals_verifier": false` (separate-agent verification,
  never self-certified), `"final_node_state": "CERTIFIED"`,
  `"lease_released": true`.
- `--demo-root/origination/origination.json`'s record for this identity
  now has `"state": "TERMINAL"`, `"terminal_node_state": "CERTIFIED"`.
- `--demo-root/loop/...` now shows `"phase": "IDLE"`.

## Second termination step

Same as above — Process B's subprocess exits normally after printing
its receipt.

## Process C command

Run as part of the same script invocation, or manually per the
`process_c` block.

## Expected Process C checkpoints

- stdout line: `Process C: NO_ELIGIBLE_WORK (raw rescan still shows 1 item(s) eligible per stale source record; correctly deduped to 0)`
- `process-c-receipt.json`: `"rehydrated_from_disk": true`,
  `"raw_scan_still_shows_source_as_eligible": true` (the source
  project's roadmap record was never mutated — this is expected, not a
  bug; see ADR-033's O1 mutation-surface note), `"deduped_new_eligible_count": 0`,
  `"result": "NO_ELIGIBLE_WORK"`.

An alternative, equally valid Process C outcome exists: if
`--origination-source` is pointed at a project with a genuinely new,
untouched `READY` roadmap item (not covered by this worked example),
Process C would instead report that item as newly eligible. Both
outcomes are correct; which one occurs depends entirely on real project
evidence, never on this script.

## Verification commands

```bash
# Focused unit tests (origination package + rehydration extension):
.venv/bin/python -m pytest \
  tests/unit/test_orchestration_origination.py \
  tests/unit/test_orchestration_origination_rehydration.py \
  tests/unit/test_orchestration_autonomy_rehydration.py \
  --no-cov -v

# Lint + types:
.venv/bin/python -m ruff check src/project_atlas/orchestration/origination/ \
  src/project_atlas/orchestration/autonomy/rehydration.py \
  tests/unit/test_orchestration_origination*.py
.venv/bin/python -m mypy src/project_atlas/orchestration/origination/ \
  src/project_atlas/orchestration/autonomy/rehydration.py

# Real implementation's own suite (in EXECUTION_WORKTREE):
PYTHONPATH=src python3 -m pytest tests/ -q   # expect: N passed, 0 skipped
```

## Negative test commands

The negative/adversarial matrix lives entirely inside
`tests/unit/test_orchestration_origination.py` as parametrized/dedicated
test functions (no separate manual commands needed) — run:

```bash
.venv/bin/python -m pytest tests/unit/test_orchestration_origination.py -v --no-cov
```

and confirm every test named for a directive negative-matrix case
(`test_todo_only_never_becomes_a_fact`,
`test_speculative_readme_idea_never_becomes_a_fact`,
`test_conflicting_requirements_fail_closed_at_policy_gate`,
`test_already_completed_work_is_excluded` (both parametrizations),
`test_superseded_specification_is_excluded` (all three lifecycles),
`test_owner_blocked_work_is_excluded`,
`test_missing_acceptance_criteria_is_valid_but_not_execution_ready`,
`test_unrelated_failing_test_is_never_consulted`,
`test_stale_evidence_changes_identity`,
`test_cross_project_contamination_is_structurally_impossible`,
`test_malicious_instruction_like_project_text_is_inert_data`,
`test_unsupported_model_suggestion_no_llm_call_exists`,
`test_duplicate_discovery_is_idempotent`,
`test_restart_replay_reads_identical_record_from_disk`) passes.

## Expected artifact locations

- `docs/adr/ADR-033-phase2a-specification-backed-work-origination.md` — architecture decision.
- `src/project_atlas/orchestration/origination/` — the new package (source-fact/proposal/policy/risk/materialize/projection/pipeline).
- `src/project_atlas/orchestration/autonomy/rehydration.py` — additive cross-process rehydration extension.
- `tests/unit/test_orchestration_origination.py`, `tests/unit/test_orchestration_origination_rehydration.py` — the test evidence.
- `docs/evidence/d-phase2a/run_three_process_demo.py` — this runbook's demo script.
- `docs/evidence/d-phase2a/receipts/process-{a,b,c}-receipt.json` — one worked-example run's actual output (secret-safe: no absolute paths, no credentials).
- `docs/evidence/d-phase2a/EVIDENCE.md` — origination schema, policy schema, source-adapter contract, negative matrix, provenance/risk-classification record, IV report summary.

## Reset procedure

```bash
rm -rf /tmp/phase2a-demo /tmp/phase2a-origination-source
git -C /path/to/atlas-showcase-gamma worktree remove /tmp/phase2a-execution-worktree --force
git -C /path/to/atlas-showcase-gamma worktree prune
```

The source project's tags (`atlas-demo-v1`,
`atlas-demo-v1-gamma-roadmap-successor`) and its live checkout are never
touched by any of the above — only the throwaway extraction/worktree/
demo-root directories are removed.

## Known limitations

- **The roadmap-completion gap** (see ADR-033 and `pipeline.py`'s
  `originate_new_only` docstring): `docs/ROADMAP.md` is deliberately not
  part of an O1 leased node's authorized `mutation_surface`, so
  completing the implementation does not, by itself, update the
  roadmap's own status field. A raw `originate_all()` rescan of the
  same source therefore still reports the item as "eligible" — Process C
  and any real successor-discovery caller **must** use
  `originate_new_only()` (which dedupes against the durable
  `TERMINAL`-marked origination projection), not `originate_all()`
  directly, or it will re-propose already-completed work. This is a
  structural limitation of Phase 2A, not a bug fixed here; a future wave
  may want a distinct, appropriately-scoped "declare roadmap item done"
  authority.
- **IN_PROCESS only**: this POC does not exercise `EXTERNAL_AGENT`
  (Cursor) dispatch. `ORCH001D-012` remains externally blocked on the
  owner's Cursor account usage limit (`docs/backlog.md`), independent of
  this POC — see the final return packet's `REAL_AGENT_RESULT`.
  `ExecutionHostClass.IN_PROCESS` was already the intended
  provider-independent path before this POC (see
  `orchestration/autonomy/models.py`'s own docstring), so this is not a
  new gap this POC introduces.
- **Single evidence source kind**: the adapter recognizes exactly two
  `SourceFactKind`s (`AUTHORITATIVE_ROADMAP_ITEM` from a fenced roadmap
  record, `CORROBORATING_SPEC_TEST` from a skip/xfail-marked test file).
  Prose-only requirements/ADRs without a structured roadmap record, or
  acceptance signals other than a skip/xfail test marker (e.g. an
  acceptance-matrix table, an explicit "unimplemented" requirement
  annotation), are out of scope for this wave — see ADR-033's
  `SOURCE FACT MODEL` section.
- **Single risk class**: only O1 is autonomously executable; every
  disqualified proposal routes to a generic `OwnerGateKind` (mostly
  `D_SECURITY_GOVERNANCE_POLICY`) rather than a more finely-differentiated
  gate per disqualifying attribute — see `materialize.py`'s
  `_DISQUALIFIER_TO_GATE` mapping.
- **No CLI subcommand**: this POC is invoked via the demo script and
  direct Python API calls (`originate_all`, `originate_new_only`,
  `materialize_work_node`, `rehydrate_governor(...,
  origination_projection_store=...)`), not a new `atlas` CLI verb. Wiring
  a CLI entrypoint (mirroring `run_governor_loop_tick`) is a natural,
  small follow-up, not done here to keep this wave's diff scoped to the
  origination capability itself.

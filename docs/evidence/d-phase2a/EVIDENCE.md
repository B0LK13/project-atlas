# D-PHASE2A Evidence Package

Companion to `docs/adr/ADR-033-phase2a-specification-backed-work-origination.md`
and `POC-RUNBOOK.md`. Consolidates the durable artifacts the directive
requires: origination schema, policy schema, source-adapter contract,
negative matrix, estate description, provenance record, risk-classification
record, and the IV report summary (appended once the independent
verification pass returns).

## ORIGINATION_SCHEMA

`src/project_atlas/orchestration/origination/proposal.py::OriginationProposal`
— every field required by the directive's "ORIGINATION PROPOSAL CONTRACT"
is present:

| Directive field | Implementation field |
|---|---|
| `WORK_ID` | `work_id` |
| `PROJECT_ID` | `project_id` |
| `TITLE` | `title` |
| `INTENT` | `intent` |
| `WHY_THIS_WORK` | `why_this_work` |
| `WHY_NOW` | `why_now` |
| `SOURCE_EVIDENCE[]` | `source_evidence` (tuple of `SourceFact`) |
| `SOURCE_LOCATIONS[]` | `source_locations` |
| `AUTHORITATIVE_SOURCE` | `authoritative_source` |
| `ACCEPTANCE_EVIDENCE[]` | `acceptance_evidence` |
| `SUCCESS_CRITERIA[]` | `success_criteria` |
| `DEPENDENCIES[]` | `dependencies` |
| `BLOCKERS[]` | `blockers` |
| `CONTRADICTIONS[]` | `contradictions` |
| `PROPOSED_SCOPE` | `proposed_scope` |
| `RISK_CLASS` | `risk_class` |
| `AUTHORITY_CLASS` | `authority_class` |
| `EVIDENCE_COMPLETENESS` | `evidence_completeness` |
| `PROVENANCE` | `provenance` (`Provenance`: adapter version + consulted content digests) |
| `ORIGINATION_IDENTITY` | `origination_identity` (sha256 hex, see PROVENANCE_RECORD below) |

`why_this_work`/`why_now`/`success_criteria` are template-filled from
`SourceFact`/roadmap-item fields only (`pipeline.py::_build_outcome`) —
never free model text. All Pydantic models use `ConfigDict(extra="forbid",
frozen=True)` where appropriate, matching the rest of
`orchestration.autonomy`'s convention.

## POLICY_SCHEMA

`policy.py::PolicyResult` — `origination_proposal_valid`,
`authoritative_intent_signal`, `corroborating_signal`, `execution_ready`,
`reason` (closed enum `ExecutionReadyReason`: `READY`,
`INSUFFICIENT_ACCEPTANCE_CONTRACT`, `CONFLICTING_PROJECT_EVIDENCE`,
`OWNER_HELD_RISK`). `evaluate()` is pure and deterministic — no I/O, no
LLM call, same input always produces the same output.

## SOURCE_ADAPTER_CONTRACT

`adapter.py`:

- `eligible_roadmap_items(project_root) -> tuple[EligibleRoadmapItem, ...]`
  — reads `<project_root>/docs/ROADMAP.md`, reuses
  `project_atlas.project_roadmap._parse_fenced_record` (existing, pure,
  vault-independent parser) plus `_normalize_status`/`_normalize_lifecycle`
  (also pure), filters to `status in {NOT_STARTED, IN_PROGRESS}` and
  `lifecycle == READY`.
- `extract_authoritative_facts(project_root, project_id)` — one
  `AUTHORITATIVE_ROADMAP_ITEM` `SourceFact` per eligible item.
- `extract_corroborating_facts(project_root, project_id, evidence_paths)`
  — for each evidence path an eligible item declares, if it resolves to
  a real file and its first 200 lines match
  `^\s*pytestmark\s*=\s*pytest\.mark\.(skip|xfail)\s*\(`, one
  `CORROBORATING_SPEC_TEST` fact. Regex only — never imports/executes
  the scanned file.

**Genericity proof (TASK_017_SPECIAL_CASES = 0)**: none of
`adapter.py`, `pipeline.py`, `policy.py`, `risk.py`, `materialize.py`,
`projection.py`, or `rehydration.py`'s origination extension contain the
string "TASK-017", "task-017", "Gamma", or any Gamma-estate-specific
identifier — verified by direct grep (see IV report). Every one of the
adversarial-matrix unit tests uses a synthetic `feature-x` fixture built
under `tmp_path`, and the real Gamma/TASK-017 case is exercised only
through the runbook's 3-process demo, never hardcoded into the library
code.

## NEGATIVE_MATRIX

All 14 directive-required cases, each backed by a dedicated (or
parametrized) test in `tests/unit/test_orchestration_origination.py`:

| Case | Test | Mechanism |
|---|---|---|
| `TODO_ONLY` | `test_todo_only_never_becomes_a_fact` | No fenced roadmap record -> no fact at all |
| `SPECULATIVE_README_IDEA` | `test_speculative_readme_idea_never_becomes_a_fact` | Prose-only "Later" section, no JSON fence -> no fact |
| `CONFLICTING_REQUIREMENTS` | `test_conflicting_requirements_fail_closed_at_policy_gate` | `contradictions` populated -> `CONFLICTING_PROJECT_EVIDENCE` |
| `ALREADY_COMPLETED_WORK` | `test_already_completed_work_is_excluded` (`IMPLEMENTED`, `VERIFIED_COMPLETION`) | Excluded at extraction (status filter) |
| `SUPERSEDED_SPECIFICATION` | `test_superseded_specification_is_excluded` (`CLOSED`, `MERGED`, `SUPERSEDED`) | Excluded at extraction (lifecycle filter) |
| `OWNER_BLOCKED_WORK` | `test_owner_blocked_work_is_excluded` | Excluded at extraction (status filter) |
| `MISSING_ACCEPTANCE_CRITERIA` | `test_missing_acceptance_criteria_is_valid_but_not_execution_ready` | `VALID` but `INSUFFICIENT_ACCEPTANCE_CONTRACT` |
| `UNRELATED_FAILING_TEST` | `test_unrelated_failing_test_is_never_consulted` | Only declared evidence paths are ever scanned |
| `STALE_EVIDENCE` | `test_stale_evidence_changes_identity` | Content change -> new `content_digest` -> new identity |
| `CROSS_PROJECT_CONTAMINATION` | `test_cross_project_contamination_is_structurally_impossible` | `project_id` is caller-scoped, never content-derived |
| `MALICIOUS_INSTRUCTION_LIKE_PROJECT_TEXT` | `test_malicious_instruction_like_project_text_is_inert_data` | Stored verbatim as opaque data; risk class unaffected |
| `UNSUPPORTED_MODEL_SUGGESTION` | `test_unsupported_model_suggestion_no_llm_call_exists` | Grep-verified: zero LLM/agent-invocation imports in the package |
| `DUPLICATE_DISCOVERY` | `test_duplicate_discovery_is_idempotent` | Same identity -> `persist_proposed` returns the existing row |
| `RESTART_REPLAY` | `test_restart_replay_reads_identical_record_from_disk` | Fresh read against the same store finds the identical record |

Plus the structural-completeness properties: `NO_DUPLICATE_ORIGINATION`,
`STABLE_WORK_IDENTITY`, `PROVENANCE_SURVIVES_RESTART` (identity.py +
projection.py, see PROVENANCE_RECORD below), `NO_CROSS_PROJECT_LEAK`
(same mechanism as `CROSS_PROJECT_CONTAMINATION`), `OWNER_GATE_PRESERVED`
(`test_materialize_owner_held_sets_owner_gate`, and the 9-case
`test_risk_classifier_routes_disqualifying_paths_to_owner_held`
parametrized test), `NO_UNSUPPORTED_SCOPE_EXPANSION` (risk classifier's
`success_criteria` emptiness check plus the explicit
`scope_exceeds_specification` boolean parameter — see `risk.py`).

## ESTATE_DESCRIPTION

Worked example: `atlas-showcase-gamma`, the `TASK-017` (blocked-task
dependency validation) item, from the `ATLAS-DEMO-ESTATE-001` demo
estate. Full identity, tags, and reproduction steps: `POC-RUNBOOK.md`
"Estate identity" section. No credential/secret material appears
anywhere in this estate or these receipts.

## PROVENANCE_RECORD

`identity.py::origination_identity(project_id, authoritative_source) =
sha256(f"{project_id}::{location}::{content_digest}")`. No wall-clock or
random component. `Provenance.consulted_digests` records every
`SourceFact.content_digest` that contributed to a proposal, so a later
process can confirm replay-stability without re-reading the original
source. Durable storage: `projection.py::OriginationProjection` (atomic
JSON, `AS-ORCH-ORIGINATION-PROJECTION-001`), one `OriginationRecord` per
identity, `state` transitions `PROPOSED -> MATERIALIZED -> TERMINAL`.

This run's actual provenance (see `receipts/process-a-receipt.json`):

```
origination_identity: 8e5fc3e94f6f000578a3ac115a26a482d48a4aa67bb7c6fa9200dcacd64a2ac3
work_id:               ORIG-8e5fc3e94f6f0005
authoritative_source:  docs/ROADMAP.md
acceptance_evidence:   tests/test_task_017_dependency_validation.py
```

## RISK_CLASSIFICATION_RECORD

`risk.py::classify()` — conservative, observable-attribute-only
classification (no LLM judgment call). This run's actual classification:
`O1_LOW_RISK_SPECIFICATION_BOUND_IMPLEMENTATION`, zero disqualifying
attributes, `proposed_scope = [docs/REQUIREMENTS.md,
docs/adr/ADR-0002-task-017-dependency-validation.md, src/,
tests/test_task_017_dependency_validation.py]` — every entry is either a
declared evidence path or the generic `src/` allowance triggered by a
`tests/`-prefixed evidence path (never project-specific). 9 disqualifying-path
unit tests confirm the O1/OWNER_HELD boundary for `.github/workflows`,
`requirements.txt`, `pyproject.toml`, `package.json`, `Dockerfile`,
`infra/`, `.env`, `src/auth/`, `migrations/`.

## IV_REPORT

_Appended after the independent verification pass returns — see the
final return packet for the summary verdict and this file's own git
history for the full report once added._

## CI_RECEIPT

_Appended after the exact-HEAD CI run (ruff + mypy + full pytest suite)
completes — see the final return packet._

## POST_MERGE_SEAL

Not applicable in this delivery: merge is owner-reserved per this
repository's established convention this session (see the final return
packet's `MERGE_RECEIPT(S)` field for the exact status). This section
will be completed only if/when the owner merges the PR and a post-merge
CI run is available to record here.

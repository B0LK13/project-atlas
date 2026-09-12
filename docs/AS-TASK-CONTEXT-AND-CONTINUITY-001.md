# AS-TASK-CONTEXT-AND-CONTINUITY-001 — Task context & continuity

| Field | Value |
|---|---|
| Package | **AS-TASK-CONTEXT-AND-CONTINUITY-001** |
| Status | **IMPLEMENTED** (local branch; not merge/authority) |
| Module | `project_atlas.task_context` |
| CLI | `atlas task-context …` |
| Schema | `task-context-packet` → `schemas/task-context-packet.schema.json` |

## Purpose

Compose a compact, traceable, freshness-aware context packet for one task
contract so an executing or resuming agent can see: what the task requires,
which sources matter, what is already evidenced, and what remains uncertain —
without replaying full chat histories.

## Truth boundaries

- `TASK CONTEXT PACKET ≠ AUTHORITY / ≠ DISPATCH`
- `RETRIEVED ≠ INSTRUCTION / ≠ POLICY / ≠ MUTATION-SCOPE WIDENING`
- `CONTINUATION_VIEW ≠ RESUME AUTHORIZATION`
- `AGENT_PROSE ≠ EXECUTION_EVIDENCE`
- `PACKET_SNAPSHOT ≠ LIVE_ENVIRONMENT`
- Packet budget does **not** bound total runtime context (repo instructions,
  tool schemas, session history may sit outside).
- No prompt-cache or cost savings claimed without runtime measurement.

## Commands

```bash
# Compose
atlas task-context compose \
  --contract path/to/contract.json \
  --workspace /path/to/repo \
  --evidence path/to/evidence.json \
  --budget-chars 48000 \
  --output /tmp/packet.json

# Inspect selection / provenance
atlas task-context inspect --packet /tmp/packet.json

# Budget report
atlas task-context budget --packet /tmp/packet.json

# Freshness recheck (prepare/handoff; no background monitor)
atlas task-context freshness \
  --packet /tmp/packet.json \
  --workspace /path/to/repo \
  --contract path/to/contract.json

# Diff two versions
atlas task-context diff --left a.json --right b.json

# Role views
atlas task-context export --packet /tmp/packet.json --view executor
atlas task-context export --packet /tmp/packet.json --view reviewer
atlas task-context continuation --packet /tmp/packet.json --no-workspace-inspectable
```

## Integration points

| Sibling | Integration |
|---|---|
| `AS-TASK-CONTRACT-001` / ATLAS-BACKLOG-TO-TASK-CONTRACT-001 | Optional live import of `project_atlas.orchestration.taskcontract`; otherwise `FIXTURE_LABELED` / file snapshots (`ContractSnapshot`). |
| ATLAS-EXECUTION-QUALITY-LOOP-001 | Evidence bundle adapter (`EvidenceRecord`); fixture-labeled until merged. |
| ATLAS-WORK-READINESS-AND-HANDOFF-001 | Continuation/export views are inputs to handoff prep; this package does not assign or dispatch. |
| Existing context | Reuses path guards (`atlas_contracts.paths`), schema registry, CTX/runtime budget discipline patterns, ADR-004 retrieved quarantine posture. |

## Mutation scope (this package)

```
src/project_atlas/task_context/**
src/project_atlas/schemas/task-context-packet.schema.json
src/project_atlas/schema.py          # register kind
src/project_atlas/cli.py             # wire atlas task-context
tests/fixtures/task-context-continuity/**
tests/unit/test_task_context_continuity_001.py
docs/AS-TASK-CONTEXT-AND-CONTINUITY-001.md
docs/evidence/AS-TASK-CONTEXT-AND-CONTINUITY-001/**
docs/superpowers/plans/2026-09-10-atlas-task-context-continuity.md
WORKLOG.md (append)
```

## Remaining limitations / external dependencies

1. Live `taskcontract` module may be absent on `main` — fixture adapter used.
2. Execution-quality evidence schema is fixture-labeled pending that package.
3. Token counts are **ESTIMATED** (`chars/4`); no bundled tokenizer.
4. Supplementary search requires an optional `search_hook`; v1 is explicit-refs first.
5. Does not authorize launch/replay/reset of supervisor programs.

## Tests

```bash
PYTHONPATH=src python -m pytest tests/unit/test_task_context_continuity_001.py -q
```

Hermetic; zero model calls.

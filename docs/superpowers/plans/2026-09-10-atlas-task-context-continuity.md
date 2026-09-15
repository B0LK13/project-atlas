# ATLAS-TASK-CONTEXT-AND-CONTINUITY-001 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compose compact, traceable, freshness-aware task context packets from task contracts without inventing authority or a second search index.

**Architecture:** New `project_atlas.task_context` package extends the existing context surface (`atlas context-pack` / Coder Alpha handoff patterns / AS-2.2 runtime compiler budget discipline). Consumes AS-TASK-CONTRACT-001-shaped inputs via optional real import or labeled fixtures. No dispatch, no Studio UI, no model calls.

**Tech Stack:** Python 3.12+, pydantic v2, existing `project_atlas.schema` / CLI argparse, hermetic pytest fixtures.

**Spec:** User task `ATLAS-TASK-CONTEXT-AND-CONTINUITY-001` (this session).

## Global Constraints

- Zero paid model calls; hermetic tests only.
- No push, merge, self-IV, registry reassignment, or global instruction edits.
- Mutation scope: `src/project_atlas/task_context/**`, schema, CLI wiring, fixtures/tests, package docs/evidence/WORKLOG entries.
- Retrieved content never promotes to policy/authorization/mutation scope.
- Sibling packages (task contract, execution quality, work readiness) may be unavailable — use `FIXTURE_LABELED` adapters and document boundaries.

## File map

| Path | Responsibility |
|------|----------------|
| `src/project_atlas/task_context/models.py` | Packet model, trust layers, digests |
| `src/project_atlas/task_context/select.py` | Deterministic explicit-relation selection |
| `src/project_atlas/task_context/budget.py` | Tiered budget accounting |
| `src/project_atlas/task_context/freshness.py` | Source identity + stale diagnosis |
| `src/project_atlas/task_context/views.py` | Executor / reviewer / continuation views |
| `src/project_atlas/task_context/compare.py` | Packet version diff |
| `src/project_atlas/task_context/assemble.py` | Orchestrator |
| `src/project_atlas/task_context/adapters.py` | Contract/evidence loaders (real or fixture) |
| `src/project_atlas/task_context/paths.py` | Path containment |
| `src/project_atlas/task_context/cli.py` | CLI handlers |
| `src/project_atlas/schemas/task-context-packet.schema.json` | Versioned schema |
| `tests/fixtures/task-context-continuity/` | Hermetic fixtures |
| `tests/unit/test_task_context_continuity_001.py` | Regressions |
| `docs/AS-TASK-CONTEXT-AND-CONTINUITY-001.md` | Integration + commands |

## Tasks

- [ ] Schema + models with trust-layer separation and content digest
- [ ] Selection + budget + freshness + assemble
- [ ] Views + compare + CLI
- [ ] Hermetic tests covering required failure scenarios
- [ ] Demo snapshot + docs + quality gates + handoff
---

## Mutation scope (pinned)

```
ALLOW:
  src/project_atlas/task_context/**
  src/project_atlas/schemas/task-context-packet.schema.json
  src/project_atlas/cli.py          # wire subcommands only
  src/project_atlas/schema.py       # register schema name if required
  tests/unit/test_task_context_continuity_001.py
  tests/fixtures/task-context-continuity/**
  docs/AS-TASK-CONTEXT-AND-CONTINUITY-001.md
  docs/evidence/AS-TASK-CONTEXT-AND-CONTINUITY-001/**
  docs/superpowers/plans/2026-09-10-atlas-task-context-continuity.md
  WORKLOG.md                        # append only
  docs/backlog.md                   # checkbox only if already present

DENY:
  atlas-vault-documentation/skill/**
  global agent instruction files
  sibling package ownership reassignment
  push / merge / registry / spending
```

# AS-STUDIO-A0-001 — repository reuse map

```text
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_WHOLESALE_CORE_REWRITE
REUSE_BEFORE_REIMPLEMENT
MODEL_PROVIDER != ATLAS_ARCHITECTURE
STUDIO_CRASH != AGENT_TASK_TERMINATION
```

Exact inventory for the A0 Linux read-only Studio vertical slice.
Classification: **REUSE** | **NEW** | **DO-NOT-TOUCH**.

## Truth Core / knowledge compiler / vault identity — REUSE (read)

| Path | Role |
|---|---|
| `src/project_atlas/knowledge_compiler.py` | Claim extraction, authority, conflicts (Truth Core) |
| `src/project_atlas/semantic_compiler.py` | Project-record / OKF rendering |
| `src/project_atlas/vault_identity.py` | Canonical vault identity (`.atlas/vault.json`) |
| `src/project_atlas/lineage.py` / `src/project_atlas/source_identity.py` | Durable identity |
| `src/project_atlas/domain/` + `src/project_atlas/schemas/` | Domain models + shipped schemas |
| `src/atlas_contracts/` | Shared agent-event / provenance / receipt contracts |

A0 does **not** rewrite these modules. Studio may later *project* vault state;
authority remains Core + daemon/control plane.

## Coordination F1–F16 — REUSE (programmatic import)

Package root: `scripts/atlas_dag/`. Schemas: `schemas/atlas_*.schema.json`,
`schemas/dag_snapshot_v1.schema.json`. Entry: `scripts/atlas-dag.py`
(CLI remains coordination tooling; Studio must **not** parse its stdout as protocol).

| Feature surface | Path | A0 RO slice use |
|---|---|---|
| control_view (F15) | `scripts/atlas_dag/control_view.py` | **Call** `build_global_control_view` |
| telemetry (F14) | `scripts/atlas_dag/telemetry.py` | **Call** `build_coordination_telemetry` / `build_efficiency_metrics` |
| residuals (F13) | `scripts/atlas_dag/residuals.py` | Optional inject / live residual registry |
| frontier_matrix (F12) | `scripts/atlas_dag/frontier_matrix.py` | Via control_view/telemetry deps when agent set |
| steal (F11) | `scripts/atlas_dag/steal.py` | Presentation inside control_view panels |
| handoff (F10) | `scripts/atlas_dag/handoff.py` | Inventory only in A0 (no mutation) |
| seal_plan (F09) | `scripts/atlas_dag/seal_plan.py` | Deferred/skipped in live RO (honest note) |
| dispatch (F08) | `scripts/atlas_dag/dispatch.py` | **DO-NOT-TOUCH** for Studio writes; read panels only |
| evidence_graph | `scripts/atlas_dag/evidence_graph.py` | Inventory / future projection |
| agents | `scripts/atlas_dag/agents.py` | Registry resolve for agent status |
| router | `scripts/atlas_dag/router.py` | Inventory; no Studio reimplementation |
| stack | `scripts/atlas_dag/stack.py` | Live stacks for control_view |
| events | `scripts/atlas_dag/events.py` | Schema validators + event ingest helpers |
| e2e_harden (F16) | `scripts/atlas_dag/e2e_harden.py` | Inventory; not required for A0 RO slice |
| model / gh / score / gate / frontier / receipts / evidence / emitter / verifiers | sibling modules under `scripts/atlas_dag/` | Live snapshot via `model.build_snapshot` + `GhClient` |

**Forbidden reuse pattern:** `subprocess` → `atlas-dag` CLI → parse stdout as Studio protocol.

## Control plane — REUSE (boundary inventory)

| Path | Role |
|---|---|
| `atlas-vault-documentation/agent_control/` | AS-CTRL-001 session/receipt/capability |
| `atlas-vault-documentation/skill/SKILL.md` | Governed skill contract |
| `atlas-vault-documentation/scripts/atlas_agent.py` | Control-plane CLI |
| `AGENT-BOOTSTRAP.md` | Agent bootstrap |

A0 RO slice does not mutate control-plane state. Studio crash must not imply
control-plane session termination.

## Existing LIVE_API / MCP read-only surfaces — REUSE (pattern)

| Path | Role |
|---|---|
| `src/project_atlas/api_server.py` / `app_service.py` / `web_api/` | Read-only LIVE_API (`atlas live api-serve`) |
| `src/project_atlas/mcp_server.py` / `mcp_registry.py` | Allow-listed read MCP tools |
| `src/project_atlas/ask2.py` / `knowledge_diff.py` | Read-only lenses |

A0 Studio spike is a sibling **projection** CLI (`scripts/atlas_studio/`), not a
rewrite of LIVE_API/MCP. Future A1+ may attach to the same daemon contracts.

## Explicit NEW (this package)

| Path | Role |
|---|---|
| `docs/atlas-3/studio/a0/*` | A0 foundation docs |
| `docs/adr/ADR-034-studio-daemon-authority.md` | Studio ↔ daemon authority ADR |
| `schemas/atlas_studio_snapshot_v1.schema.json` | `ATLAS_STUDIO_SNAPSHOT_V1` |
| `schemas/atlas_studio_event_v1.schema.json` | `ATLAS_STUDIO_EVENT_V1` (observation only) |
| `scripts/atlas_studio/` | Linux RO vertical slice |
| `scripts/atlas-studio.py` | Entry point |
| `tests/unit/test_atlas_studio_a0.py` | A0 contract tests |

## Explicit DO-NOT-TOUCH (A0)

- Wholesale rewrite of `src/project_atlas/` Truth Core or coordination stack.
- Studio APIs that claim / dispatch / emit / merge / IV / write vault authority.
- Treating UI cache, Studio process liveness, or model-provider choice as Atlas truth.
- Parsing `atlas` / `atlas-dag` human CLI text as a machine protocol.
- Killing daemon/agent tasks because the Studio process exited.

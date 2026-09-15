# Estate Ops — architecture (PREP)

Package: **AS-2.2-ESTATE-OPS-PREP-001**  
Status: **PREP ONLY** — no runnable estate-ops engine on main.

## Problem

Estate-scale operators need a **single read-only cockpit** spanning Mission
Control (work routing), Workspace (active slices), and Ops Health (operational
rollup) across multiple projects — without confusing UI panels, MCP reads, or
LLM summaries with Layer B authority.

## Layers

```text
Layer A — source evidence (vault imports, receipts, diagnostics)
        |
        v
Layer B — canonical OKF / claims / authority (NEVER written by this PREP)
        |
        v
Layer C — derived estate-ops projections (this PREP sketches contracts)
        |
        +--> Mission Control lens (routing / queue chips)
        +--> Workspace lens (active slice cards)
        +--> Ops Health receipt (rollup + signal chips)
```

## Data flow (consume-only)

```text
AS-OBS-001 health snapshot ----\
AS-XPROJ estate lens -----------> EstateOpsCockpitView (derived)
Web lens stubs (MC/WS/Ops) -----/
        |
        v
Operator panel (read-only) + propose-only EstateOpsAction
        |
        X (forbidden) --> Layer B / ops_health mutation / canonical write
```

## Composition

| Input family | Owner | Estate-ops use |
|---|---|---|
| `ops_health` | AS-OBS-001 | Rollup chips; unknown when evidence absent |
| `xproj_estate_lens` | AS-2.2-XPROJ-001 | Multi-project scope + cited_ids |
| `mission_control` | AS-WEB-MISSION-CONTROL-001 | Route-level lens card |
| `workspace` | AS-WEB-WORKSPACE-001 | Active slice card |
| `mcp_ops_read` | MCP-001 | `atlas.ops.health.read` citation |

## Truth boundaries

- **EstateOpsCockpitView** — derived envelope; `authority.level = derived`
- **MissionControlLens** — consume-only queue projection; never promotes tasks
- **OpsHealthReceipt** — operational plane only; `OPERATIONAL HEALTH ≠ PROJECT AUTHORITY`
- **EstateOpsAction** — propose / escalate only; reject canonical_write

## Non-claims

- Not WEB APPLICATION ACCEPTED evidence
- Not authentic estate PILOT PASS
- Not `ATLAS_2_1_RELEASE_CERTIFIED`
- Not live provider bridge default-on
- Prep fixtures use synthetic `harbor-*` demo ids only

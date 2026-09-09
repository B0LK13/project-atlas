# AS-STUDIO-A1 — scope reconciled from repository truth

```text
STUDIO_UI != AUTHORITY
UI_STATE = PROJECTION_OF_ATLAS_TRUTH
NO_CLI_TEXT_PARSING_AS_PROTOCOL
NO_PARALLEL_CONTROL_PLANE
REUSE_BEFORE_REIMPLEMENT
STALE_UI_STATE != CURRENT_TRUTH
AS_STUDIO_A1_IMPLEMENTATION = NOT_STARTED
```

This document **challenges** earlier A1 planning where repository truth
diverges. It does not implement A1.

## What changed since #746 / PHASES wording

| Prior planning | Repository truth | Reconciled A1 stance |
|---|---|---|
| A1 implies desktop Mission Control (Tauri) early | A0 already ships typed RO projection CLI over F14/F15/F13; no Tauri stack in-repo | **A1.0 = useful RO Mission Control projection** (CLI/TUI or thin view). Tauri is **optional shell** (A1.1 / separate ADR), not a prerequisite for Mission Control usefulness |
| Need new Studio eligibility/ownership engines | F15 `ATLAS_GLOBAL_CONTROL_VIEW_V1` already panels: agents, ownership, stacks, frontier, residuals, telemetry, steal, dispatch_gates, evidence_health, postmerge, event_bus, system_honesty | **Present and explain F15 panels** — do not reimplement |
| “Daemon data” means atlasd only | No `atlasd` binary yet; live truth is coordination builders + GhClient | Pending **O1** in A0-CLOSURE; design assumes interim in-process control plane unless owner requires atlasd first |
| A1 starts after vague A0 acceptance | A0 is `TECHNICALLY_COMPLETE` with explicit owner decisions | A1 **design READY**; implementation waits on O1 (or owner waive) |

## Mission Control outcomes A1 must deliver

A user must answer these **without reconstructing state manually**, from one
Studio Mission Control surface fed by typed snapshots:

1. What Atlas coordination is doing now (lanes / stacks / event bus health).
2. Which agents exist and registration/activity status.
3. What is runnable vs blocked (frontier classes + dispatch gates).
4. Ownership and freeze/gate state.
5. CI / IV posture (including `EXTERNAL_IV_GATED` honesty).
6. Residual work that still exists.
7. Telemetry / efficiency (as projection, not authority).
8. Stack topology and postmerge/seal notes (honest about deferred seal scan).
9. Evidence/freshness of the view (`generated_at_utc`, fingerprint, stale).
10. What needs **human attention** (owner decisions, IV unbound, blocked high-value work, residuals).

## Non-goals (A1)

- Claim / dispatch / handoff / merge / IV write (A2+).
- Knowledge Plane / Improvement Plane runtimes (A5/A7).
- Parallel control plane or CLI-text protocol.
- Rewriting A0 contracts or ADR-034.
- Assuming merge of #762/#763/#751.

## Valid requirements (kept)

From REQUIREMENTS-REGISTER: **06**, **13–14**, **18**, **25**, **29**, **55**
remain load-bearing for A1, interpreted as **projection over F1–F16**.

## Deferred / reshaped

| Item | Action |
|---|---|
| Req 03 Tauri stack | Defer shell choice; not the A1.0 usefulness gate |
| Req 05 full nav IA | Out of A1.0 — Mission Control first, not full workstation chrome |
| Req 04 atlasd process split | Owner **O1**; A1.0 may proceed under O1a |
| Seal completeness | Surface F15 honesty; do not fake seal PASS |

## Dependency

```text
A0 TECHNICALLY_COMPLETE (done)
+ F1–F16 control plane available on implementation tip (done at #751 lineage)
+ O1 answered or waived → A1 implementation may start
```

# AS-STUDIO-A0-001 — technical closure

```text
AS_STUDIO_A0_001 = TECHNICALLY_COMPLETE
IMPLEMENTED != MERGED
CI_PASS != FORMAL_IV
MERGE_AUTHORIZATION = NOT_GRANTED
STUDIO_UI != AUTHORITY
ATLAS_DAEMON = AUTHORITATIVE_RUNTIME
```

Audited against fresh repository/GitHub truth (2026-09-09) for
`CLOSE_ATLAS_STUDIO_A0_AND_PREPARE_A1`.

## Exact implementation object

| Field | Value |
|---|---|
| PR | https://github.com/B0LK13/project-atlas/pull/763 |
| Branch | `feat/as-studio-a0-001` |
| Base | `feat/atlas-dag-e2e-harden` (#751) — F1–F16 tip |
| HEAD (closure audit) | `7419593c007e2d3ebb1b9fc99085eba94bfbe936` |
| Exact-head CI | **PASS** run `34324941540` |
| Local contract tests | `tests/unit/test_atlas_studio_a0.py` — 11 passed |
| ADR | [ADR-034](../../../adr/ADR-034-studio-daemon-authority.md) |
| Evidence | [EVIDENCE.md](./EVIDENCE.md) |

## Architecture verdict (defensible)

A0 remains the correct foundation:

1. Studio is a **projection** (`ATLAS_STUDIO_SNAPSHOT_V1` / observation events).
2. Authority stays with coordination/control-plane builders and future daemon
   paths — **not** Studio UI process liveness.
3. Protocol is **typed JSON schemas**, never CLI text parsing.
4. RO slice reuses F14/F15/F13 programmatically; no parallel eligibility engine.
5. Mutation surfaces are absent by design (authz + tests).

No material technical defect found that requires rewriting A0 before A1 design.
Minor productization gaps (explicit stale TTL, first-class Mission Control
panel layout, dedicated `atlasd` process) are **A1 / owner-scope**, not A0
blockers for `TECHNICALLY_COMPLETE`.

## Coherence check (ADR ↔ schemas ↔ code)

| Check | Result |
|---|---|
| ADR-034 authority laws present in honesty block | PASS |
| Schema requires RO honesty consts | PASS |
| No claim/dispatch/merge/kill APIs in `atlas_studio` | PASS |
| Live path imports `atlas_dag` builders (no subprocess protocol) | PASS |
| Nested F15 `control_view` panels available inside snapshot | PASS |
| Separate long-running `atlasd` binary shipped | **NO** — see owner decisions |

## Canonical Studio package status (truthful)

| Object | Status |
|---|---|
| Docs PR #762 vs `main` | **OPEN** @ `ff9af182221fc7847f732e8c65366337ad88dc8c`; exact-head CI **PASS** `34330650940`; **not** merged |
| Package path | `docs/atlas-3/studio/` (also present on A0 tip via merge) |
| Vault MDA normalize/route/receipt | **PENDING** (production `mda` unavailable; not fabricated) |
| Stamp | `STUDIO_CANONICAL_PACKAGE_STATUS = REPO_SYNCHRONIZED_PR_OPEN` |

Do **not** treat #762 as `MERGED_TO_MAIN`.

## Technical defects remaining

| Severity | Item | Disposition |
|---|---|---|
| None Critical/Major | — | — |
| Minor (A1) | Snapshot lacks explicit `freshness` / stale-after TTL fields | Own in A1 (`STALE_UI_STATE != CURRENT_TRUTH`) |
| Minor (A1) | Mission Control human layout not productized (panels nested under F15) | Own in A1 |
| Honest limit | Live seal scan often deferred (`skipped_for_latency`) | Inherit F14/F15 honesty; surface in A1 postmerge panel notes |

## A0_REMAINING_OWNER_DECISIONS (explicit)

These are **not** technical blockers for A0 closure. A1 **implementation**
must not start until the architectural gate below is answered (or owner
explicitly waives and accepts interim interpretation).

### O1 — What is `ATLAS_DAEMON` for A1 transport? (**architectural gate**)

Current truth: A0 “live” path runs coordination builders **in-process** via
`GhClient` / `atlas_dag` (same process as `atlas-studio`). There is **no**
separate `atlasd` service yet. ADR-034 already allows “daemon / coordination
control plane” as authority.

Owner must choose for A1:

- **O1a** Accept in-process coordination control plane as interim authoritative
  runtime for RO Mission Control (A0 interpretation continues); dedicated
  `atlasd` deferred to A2/A3.
- **O1b** Require a real `atlasd` (or LIVE_API-style long-lived service)
  before any A1 Mission Control UI/CLI productization beyond A0.

Until O1 is answered, default for **design** is O1a (matches shipped A0), and
`AS_STUDIO_A1_IMPLEMENTATION = NOT_STARTED`.

### O2 — Merge sequencing

Owner decides when to merge #762 (docs→main), #763 (A0, stacked on #751), and
the F1–F16 stack. Studio A1 depends on F1–F16 primitives remaining available;
`IMPLEMENTED != MERGED`.

### O3 — Formal IV

External IV for A0 / coordination stack remains unbound unless owner assigns
verifiers. `CI_PASS != FORMAL_IV`.

### O4 — Vault MDA

Production MDA normalize/route/receipt for intake
`AS-STUDIO-INTAKE-20260908-01` remains owner/environment gated.

### O5 — A1 shell preference (product, not A0 architecture)

#746 prefers Tauri 2 desktop. Repo truth: A0 CLI projection already works.
Owner may prefer CLI/TUI Mission Control first (recommended smallest A1) vs
Tauri-now. See `../a1/A1-FIRST-WORK-PACKAGE.md`.

## Closure stamps

```text
AS_STUDIO_A0_001 = TECHNICALLY_COMPLETE
A0_REMAINING_OWNER_DECISIONS = EXPLICIT
STUDIO_CANONICAL_PACKAGE_STATUS = REPO_SYNCHRONIZED_PR_OPEN
ATLAS_STUDIO_A1_IMPLEMENTATION = NOT_STARTED
MERGE_AUTHORIZATION = NOT_GRANTED
```

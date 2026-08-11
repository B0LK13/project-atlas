# AS-PROD-INSTALL-ADV-001 — Findings

| Field | Value |
|---|---|
| Package | L03 / AS-PROD-INSTALL-ADV-001 |
| Tip base | `6709503` (#255) |
| Evidence | `D:\project-atlas-orphans\atlas-2.1-productionization-001\productization-wave1\L03\` |
| Honesty | PRODUCTIZATION · NOT RELEASE · NOT PILOT · ALPHA_READY=NO |

## Empirical journeys (LOCAL)

| Journey | Result | Notes |
|---|---|---|
| Preflight | **PASS** | Python/Node/npm/.tmp OK (~2s) |
| Start alt ports (18765/15173) | **PASS** | API `/v1/meta` + web health; `STRANGER_CAN_START_ATLAS=YES` (local) |
| Default port collision (8765 busy) | **FAIL→REMEDI** | Pre-remedi could false-health foreign listener |
| Post-remedi collision | **PASS** | Structured WHAT/CAUSE/ACTION/RETRY; exit 1 |
| Post-remedi clean start | **PASS** | See `postremedi-start-success-*.txt` |

## PROD-FINDING-###

### PROD-FINDING-001 — HIGH (remediated)

| Field | Value |
|---|---|
| Severity | **HIGH** (remediated in this PR) |
| Surface | `scripts/windows/atlas-start.ps1`, `_AtlasCommon.ps1` |
| Observation | When API/web ports already had a loopback listener, start could attach health to a foreign process. |
| Fix | Preflight port-free check + ownership check; fail closed with product error. |
| Status | **CLOSED** by remedi in L03 PR |

### PROD-FINDING-002 — MEDIUM

| Field | Value |
|---|---|
| Severity | **MEDIUM** |
| Surface | `apps/web` npm install on Windows |
| Observation | Fresh installs need Rollup win32 optional native + esbuild script approval; `atlas-start` attempts Rollup optional install but does not commit `package.json` deps (Cloud #253 owns web package matrix). |
| Status | **OPEN** — operational note; no `package.json` mutation in this lane |

### PROD-FINDING-003 — LOW

| Field | Value |
|---|---|
| Severity | **LOW** |
| Surface | Default ports 8765/5173 |
| Observation | Busy developer machines often collide; strangers should use `-ApiPort`/`-WebPort` or `atlas-stop`. |
| Status | **OPEN** — documented in STRANGER path / error text |

## Verdict

| Claim | Value |
|---|---|
| **STRANGER_CAN_START_ATLAS** | **YES** (LOCAL empirical — alt-port + post-remedi success) |
| CRITICAL open | **0** |
| HIGH open | **0** (001 remediated) |
| ATLAS_DESIGN_PARTNER_ALPHA_READY | **NO** |
| PILOT | **DORMANT_BLOCKED** |

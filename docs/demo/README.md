# Atlas Technical Demo — docs index

| Field | Value |
|---|---|
| Package | **AS-DEMO-2.1-001** |
| Class | `TECHNICAL_PREVIEW` / `NON_RELEASE_CERTIFICATION` |
| Directive | `D-PROJECT-ATLAS-HARVEST-DEMO-POC-001` |
| Honesty rule | **TECHNICAL DEMO — VERIFIED** ≠ **RELEASE CERTIFIED**; `DEMO_FIXTURE` ≠ authentic pilot; **PILOT DORMANT** |

## Read first

1. [`AS-DEMO-2.1-001.md`](AS-DEMO-2.1-001.md) — normative charter
2. [`MODE-BANNER.md`](MODE-BANNER.md) — required operator / UI / launcher banner text

## Required labels

Every demo doc, launcher, surface, and receipt under this tree must remain
honest:

```text
DEMO
NOT AUTHENTIC PILOT
NOT RELEASE EVIDENCE
```

When demo gates pass, the only allowed certificate headline is:

```text
TECHNICAL DEMO — VERIFIED
```

with the explicit companion lines:

```text
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
```

## Tree (owned + expected sibling surfaces)

| Path | Role | Sole writer |
|---|---|---|
| `AS-DEMO-2.1-001.md` | Charter | D01 |
| `README.md` | This index | D01 |
| `MODE-BANNER.md` | Honest mode banners | D01 |
| `scripts/` | Windows-first launchers | D02 |
| `WINDOWS-QUICKSTART.md` | Windows operator path | D02 |
| `fixtures/` | `DEMO_FIXTURE` corpus | D03 |
| `BACKEND-SUITE.md` / `checklists/backend.md` | Backend gate runbook | D04 |
| `FRONTEND-SUITE.md` / `checklists/frontend.md` | Web + E2E path | D05 |
| `browser-e2e/` (`AS-DEMO-2.1-BROWSER-E2E-001`) | Isolated `BROWSER_E2E_MISSING` harness (≠ auto VERIFIED) | Demo browser-E2E package |
| `API-MCP-E2E.md` / `checklists/api-mcp.md` | Live smoke + MCP consistency | D06 |
| `L3-OAI-OPTIONAL.md` | Non-blocking optional lane | D07 |
| `ADV-DEMO.md` / `CERTIFICATE-TEMPLATE.md` | ADV + cert template | D08 |

Sibling paths may land on separate branches/PRs. Do not dual-write another
worker's sole-writer surface.

## Modes

| Mode | Env | Purpose |
|---|---|---|
| A (default) | `ATLAS_DEMO_MODE=fixture` | Deterministic `DEMO_FIXTURE` Technical Preview |
| B (optional) | `ATLAS_DEMO_ROOT=<path>` | Legitimate live project root; still not automatic pilot pass |

See `MODE-BANNER.md` for the exact banner strings each mode must print.

## Release / pilot firewall

| Gate | Demo lane value |
|---|---|
| Technical Demo certificate | May become **TECHNICAL DEMO — VERIFIED** |
| `ATLAS_2_1_RELEASE_CERTIFIED` | Remains **NO** until authentic release path |
| Authentic estate pilot | Remains **PILOT DORMANT** / `DORMANT_BLOCKED` |
| `v2.1.0` | Not unlocked by demo success |

## Evidence

Coordinator / orphan evidence root:

`D:\project-atlas-orphans\atlas-2.1-productionization-001\`

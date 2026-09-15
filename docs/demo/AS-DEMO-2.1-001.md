# AS-DEMO-2.1-001 — Technical Preview Charter

| Field | Value |
|---|---|
| Package | **AS-DEMO-2.1-001** |
| Class | `TECHNICAL_PREVIEW` / `NON_RELEASE_CERTIFICATION` |
| Directive | `D-PROJECT-ATLAS-HARVEST-DEMO-POC-001` |
| Demo cert target | **TECHNICAL DEMO — VERIFIED** |
| Release cert | **NOT RELEASE CERTIFIED** |
| Pilot status | **PILOT DORMANT** (`DORMANT_BLOCKED`) |
| Authentic pilot | **NOT AUTHENTIC PILOT PASS** |
| Fixture class | `DEMO_FIXTURE` ≠ authentic estate |
| Core runtime mutation | **FORBIDDEN** for this package |

## Purpose

Produce the first fully verified Project Atlas **Technical Demo / PoC** on a
deterministic `DEMO_FIXTURE` estate, without confusing demo success with Atlas
2.1 release certification or authentic-estate pilot pass.

This charter is the normative honesty contract for all AS-DEMO-2.1-001 workers
(D01–D08) and for any human or agent operator running the demo.

## Normative inequalities (fail closed)

| Demo claim | Must never be read as |
|---|---|
| **TECHNICAL DEMO — VERIFIED** | **RELEASE CERTIFIED** / `v2.1.0` |
| `DEMO_FIXTURE` success | Authentic estate **PILOT PASS** |
| Demo E2E green | `ATLAS_2_1_RELEASE_CERTIFIED = YES` |
| Mode A fixture corpus | Real customer / portfolio estate |

Explicit labels required on every demo surface (docs, launcher, UI banner,
receipts, certificates):

```text
DEMO
NOT AUTHENTIC PILOT
NOT RELEASE EVIDENCE
```

Certificate wording when demo gates pass:

```text
TECHNICAL DEMO — VERIFIED
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
```

## Pilot firewall

| Gate | Value |
|---|---|
| `AUTHENTIC_ESTATE_ROOT` | empty (until owner supplies) |
| `AS-2.1-PILOT-AUTH-001` | **DORMANT_BLOCKED** |
| `ACTIVE_PILOT_WORKER` | **NONE** |
| Wake event | `AUTHENTIC_ESTATE_ROOT_AVAILABLE` |

Technical demo success **does not** clear the authentic pilot gate and **does
not** unlock `AS-REL-2.1-001` / `v2.1.0`.

When an authentic root arrives, wake pilot → sync/twin-auth → live E2E → RC
ADV/SECURITY → release path **independently** of this demo package.

## Two demo modes

See `MODE-BANNER.md` for operator-facing banner text.

### Mode A — deterministic demo (default for Technical Preview)

```text
ATLAS_DEMO_MODE=fixture
```

- Uses an intentionally designed representative project estate under an
  explicitly named fixture/demo path (`docs/demo/fixtures/` and related
  DEMO_FIXTURE packs owned by sibling workers).
- Sufficient for **TECHNICAL DEMO — VERIFIED**.
- Never invents `.atlas-project.yaml` inside a real project to fake authentic
  pilot status.

### Mode B — live project (optional later)

```text
ATLAS_DEMO_ROOT=<real project root>
```

- Allowed only when a legitimate project root is available.
- May later feed authentic pilot work **only if** that work independently
  satisfies pilot rules.
- Mode B alone does not grant **PILOT PASS** or release certification.

## Demo story (normative outline)

The demo tells one coherent story (not random screens):

1. Discover projects
2. Ingest project evidence
3. Build governed knowledge
4. Open Command Center — projects appear
5. Open a project — evidence-backed knowledge
6. Ask Atlas — answer + evidence, or UNKNOWN / CONFLICT
7. Open Graph — cross-project relationship
8. Introduce conflicting / stale evidence — refuse false certainty
9. Mission Control / Workspace — operational state
10. MCP reads the same knowledge as the API
11. Controlled operation executes — receipt reconstructs what happened

### Hero scenario (fixture)

- Project A documentation: PostgreSQL 15
- Project A implementation evidence: PostgreSQL 16
- Project B depends on Project A API

Atlas must demonstrate conflict/stale handling, authority precedence, graph
dependency / impact visibility, explicit unknown where needed, and provenance.
Do **not** fabricate a winner without Atlas authority evidence.

## Certification envelope

| Outcome | Meaning |
|---|---|
| **TECHNICAL DEMO — VERIFIED** | Clean-clone path, backend/frontend gates, live API smoke, MCP consistency, and browser/demo E2E (or recorded `BROWSER_E2E_MISSING` + isolated package) all pass under honest DEMO labels |
| **NOT RELEASE CERTIFIED** | Demo does not satisfy `v2.1.0` release certification |
| **NOT AUTHENTIC PILOT PASS** | Demo fixture / Mode B sample ≠ authentic estate pilot |

CRITICAL/HIGH `DEMO-FINDING-###` items must be remediated before claiming
**TECHNICAL DEMO — VERIFIED**.

## Non-goals

- Mutating Core runtime (`src/project_atlas/**`) under this package ID
- Waiving authentic estate PILOT for release
- Treating fixture receipts as release evidence
- Blocking 2.2 prep lanes (Hybrid Retrieval, Context Compiler, Memory, KCI,
  DoD, Time Machine, Reality Gap, Research)

## Sibling ownership (do not dual-write)

| Surface | Owner |
|---|---|
| `docs/demo/AS-DEMO-2.1-001.md`, `README.md`, `MODE-BANNER.md` | **D01** (this package) |
| Windows launcher / quickstart | D02 |
| `docs/demo/fixtures/**` | D03 |
| Backend suite runbook | D04 |
| Frontend runbook | D05 |
| API/MCP E2E docs | D06 |
| L3/OAI optional demo | D07 |
| ADV + certificate template + phrase tests | D08 |

## Status at charter land

| Gate | Value |
|---|---|
| `TECHNICAL_PREVIEW` docs | **IN PROGRESS** (charter) |
| `TECHNICAL DEMO — VERIFIED` | **NO** (not yet earned) |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |
| Pilot | **DORMANT** |

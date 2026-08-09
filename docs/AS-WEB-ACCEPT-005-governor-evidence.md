# AS-WEB-ACCEPT-005 - Governor evidence pack

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-005 |
| Parent | D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001 |
| Evidence baseline | MAIN `bfdc5862b46c7e8da8fff26224fac8b7b6a2f59f` / TREE `fa404c270c1659d4c48739440a43087a4226b939` |
| **WEB APPLICATION ACCEPTED** | **NO** |
| Governor decision | **PENDING** |

## Purpose

This pack collects reproducible automated evidence for criteria 1-9, 12, and 13.
It does not complete human governor item 10. Automated PASS results are necessary
but not sufficient to change the acceptance decision.

## Automated evidence map

| # | Automated criterion | Evidence | Expected result |
|---|---|---|---|
| 1 | Production and design-lab routes are present | `node apps/web/scripts/smoke.mjs` | PASS |
| 2 | UI, graph, and unknown-state invariants hold | smoke stub and production-page checks | PASS |
| 3 | ADR-008, ADR-009, and ADR-010 are present | smoke and checklist unit tests | PASS |
| 4 | `web_api` remains read-only | smoke import guard and `test_as_web_001_web_api.py` | PASS |
| 5 | Command Center modes are present | smoke source checks | PASS |
| 6 | Design-lab themes are retained | smoke token checks | PASS |
| 7 | Knowledge and Graph production lenses exist | smoke and fixture read-adapter tests | PASS |
| 8 | Production shell has an accessibility skip-link | smoke source checks | PASS |
| 9 | Fixture E2E read bundle covers projects, knowledge, graph, and health | `test_as_web_accept_002_closeout.py` | PASS |
| 12 | Mission Control and Workspace routes preserve non-authority semantics | smoke route, page, and stub checks | PASS (non-certifying) |
| 13 | Ops Health receipt micro-lens is read-only and honest about unavailable evidence | smoke page and stub checks | PASS (non-certifying) |

## Reproduction commands

Run from the repository root at the pinned baseline:

```powershell
git rev-parse origin/main
git rev-parse 'origin/main^{tree}'
node apps/web/scripts/smoke.mjs
D:\atlas-worktrees\as-core-006-postmerge-verify\.venv\Scripts\python.exe -m pytest tests/unit/test_as_web_001_web_api.py tests/unit/test_as_web_accept_001_checklist.py tests/unit/test_as_web_accept_002_closeout.py tests/unit/test_as_web_accept_003_signoff_pack.py tests/unit/test_as_web_accept_005_governor_evidence.py -q
```

Expected pin output:

```text
bfdc5862b46c7e8da8fff26224fac8b7b6a2f59f
fa404c270c1659d4c48739440a43087a4226b939
```

Expected gate outcomes:

```text
AS-WEB-ACCEPT-004 smoke PASS — ops-health receipts + mission-control + workspace + knowledge/graph + a11y skip + ADRs (ACCEPTED=NO)
pytest: all selected tests PASS
```

## Human governor boundary

Criterion 10 remains open in `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md`.
A human governor must review the evidence, record the reviewed tip and tree, and
make the decision. This pack supplies no signature and grants no acceptance.

## Explicit non-claims

- WEB APPLICATION ACCEPTED = **NO**
- Governor decision = **PENDING**
- RELEASE CERTIFIED = **NO**
- ESTATE PILOT PASSED = **NO**

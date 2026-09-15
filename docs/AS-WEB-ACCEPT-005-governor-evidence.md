# AS-WEB-ACCEPT-005 - Governor evidence pack

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-005 |
| Parent | D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001 |
| Evidence baseline | MAIN `8ee65b91871bc04039ffe401a9da3743e4800a8b` / TREE `a2e592a797056935fbec0d8c54033aa3c25a5b06` |
| **WEB APPLICATION ACCEPTED** | **YES** |
| Governor decision | **APPROVED** |

## Purpose

This pack collects reproducible automated evidence for criteria 1-9, 12, and 13
and records the tip used for the owner-authorized item-10 decision.

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
| 12 | Mission Control and Workspace routes preserve non-authority semantics | smoke route, page, and stub checks | PASS |
| 13 | Ops Health receipt micro-lens is read-only and honest about unavailable evidence | smoke page and stub checks | PASS |

## Reproduction commands

Run from the repository root at the pinned baseline:

```powershell
git rev-parse origin/main
git rev-parse 'origin/main^{tree}'
node apps/web/scripts/smoke.mjs
npm --prefix apps/web run build
D:\atlas-worktrees\as-core-006-postmerge-verify\.venv\Scripts\python.exe -m pytest tests/unit/test_as_web_001_web_api.py tests/unit/test_as_web_accept_001_checklist.py tests/unit/test_as_web_accept_002_closeout.py tests/unit/test_as_web_accept_003_signoff_pack.py tests/unit/test_as_web_accept_005_governor_evidence.py -q
```

Evidence pin (pre-stamp tip used for fresh verify):

```text
8ee65b91871bc04039ffe401a9da3743e4800a8b
a2e592a797056935fbec0d8c54033aa3c25a5b06
```

Expected gate outcomes:

```text
AS-WEB-ACCEPT-004 smoke PASS — … (ACCEPTED=YES after stamp)
pytest: all selected tests PASS
npm run build: PASS
```

## Human governor boundary

Criterion 10 is **closed — APPROVED** in `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md`
under directive `D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001` after
fresh tip verification (prior pin drifted; gates re-run green).

## Explicit claims / non-claims

- WEB APPLICATION ACCEPTED = **YES**
- Governor decision = **APPROVED**
- RELEASE CERTIFIED = **NO**
- ESTATE PILOT PASSED (authentic / production) = **NO**

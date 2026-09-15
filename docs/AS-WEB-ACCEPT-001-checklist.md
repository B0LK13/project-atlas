# AS-WEB-ACCEPT-001 — Web application acceptance checklist

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-001 through AS-WEB-ACCEPT-006 (owner-gates closeout) |
| Parent | D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001 |
| Tip pin | `8ee65b91871bc04039ffe401a9da3743e4800a8b` / TREE `a2e592a797056935fbec0d8c54033aa3c25a5b06` |
| **WEB APPLICATION ACCEPTED** | **YES** |
| Governor sign-off | **APPROVED** — see `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` |

## Normative invariants (ADR-008)

- **UI ≠ canonical**
- **Graph ≠ authority**
- **Unknown ≠ healthy**

Acceptance does **not** make the UI canonical. ADR-008 invariants remain normative.

## Checklist

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | Production shell routes smoke green (`/`, `/projects`, `/knowledge`, `/graph`, `/ops`, `/command-center`, `/mission-control`, `/workspace`, design-lab) | `apps/web/scripts/smoke.mjs` | automated PASS |
| 2 | Stub + UI enforce UI≠canonical / Graph≠authority / Unknown≠healthy | sample stub + production pages | automated PASS |
| 3 | ADR-008 / ADR-009 / ADR-010 present | smoke + unit tests | automated PASS |
| 4 | `web_api` read-only boundary intact | `web_api/`, tests | automated PASS |
| 5 | Command Center modes present | CommandCenterPage + smoke | automated PASS |
| 6 | Design-lab themes retained | design-lab routes + tokens | automated PASS |
| 7 | Knowledge + Graph production lenses | `/knowledge`, `/graph` + `web_api.knowledge` / `web_api.graph` | automated PASS |
| 8 | a11y skip-link on production shell | `ProdShell` + CSS `:focus` | automated PASS |
| 9 | Fixture E2E read bundle (projects/knowledge/graph/health) | `test_as_web_accept_002_*` | automated PASS |
| 10 | Governor sign-off artifact + tip pin recorded | `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` | **closed — APPROVED** |
| 11 | CI / local smoke invocation documented | `apps/web/README.md` | documented |
| 12 | Mission Control + Workspace lenses (route presence only) | `#/mission-control`, `#/workspace` + smoke/unit | automated PASS |
| 13 | Ops Health receipt micro-lens (read-only unknown stub) | `#/ops` + smoke/unit | automated PASS |

## Automated gates (evidence)

```bash
node apps/web/scripts/smoke.mjs
npm --prefix apps/web run build
python -m pytest tests/unit/test_as_web_001_web_api.py tests/unit/test_as_web_accept_001_checklist.py tests/unit/test_as_web_accept_002_closeout.py tests/unit/test_as_web_accept_003_signoff_pack.py tests/unit/test_as_web_accept_005_governor_evidence.py -q
```

## Explicit claims / non-claims

- WEB APPLICATION ACCEPTED = **YES**
- RELEASE CERTIFIED = **NO**
- PILOT estate rows are not invented by the web shell.
- Authentic / production estate PILOT remains separate from WEB acceptance.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial checklist draft (ACCEPTED=NO) |
| 2026-08-09 | WEB-ACCEPT-002 through WEB-ACCEPT-005 evidence packs (ACCEPTED=NO) |
| 2026-08-10 | Owner-gates closeout: fresh tip verify + governor APPROVED (ACCEPTED=YES) |

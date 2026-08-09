# AS-WEB-ACCEPT-001 — Web application acceptance checklist

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-001 / AS-WEB-ACCEPT-002 closeout |
| Parent | D-PROJECT-ATLAS-1.0-FINISH-PLUS-2.0-PREP-001 |
| Tip pin | pending merge tip |
| **WEB APPLICATION ACCEPTED** | **NO** |
| Governor sign-off | **PENDING** (automated gates ≠ ACCEPTED) |

## Normative invariants (ADR-008)

- **UI ≠ canonical**
- **Graph ≠ authority**
- **Unknown ≠ healthy**

## Checklist

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | Production shell routes smoke green (`/`, `/projects`, `/knowledge`, `/graph`, `/ops`, `/command-center`, design-lab) | `apps/web/scripts/smoke.mjs` | automated |
| 2 | Stub + UI enforce UI≠canonical / Graph≠authority / Unknown≠healthy | sample stub + production pages | automated |
| 3 | ADR-008 / ADR-009 / ADR-010 present | smoke + unit tests | automated |
| 4 | `web_api` read-only boundary intact | `web_api/`, tests | automated |
| 5 | Command Center modes present | CommandCenterPage + smoke | automated |
| 6 | Design-lab themes retained | design-lab routes + tokens | automated |
| 7 | Knowledge + Graph production lenses | `/knowledge`, `/graph` + `web_api.knowledge` / `web_api.graph` | automated |
| 8 | a11y skip-link on production shell | `ProdShell` + CSS `:focus` | automated |
| 9 | Fixture E2E read bundle (projects/knowledge/graph/health) | `test_as_web_accept_002_*` | automated |
| 10 | Governor sign-off artifact + tip pin recorded | evidence package | **open** |
| 11 | CI smoke invocation documented | `apps/web/README.md` | draft |

## Automated gates (non-certifying)

```bash
node apps/web/scripts/smoke.mjs
python -m pytest tests/unit/test_as_web_001_web_api.py tests/unit/test_as_web_accept_001_checklist.py tests/unit/test_as_web_accept_002_closeout.py -q
```

Passing automated gates is necessary but **not sufficient** for WEB APPLICATION ACCEPTED
while item 10 (governor sign-off) remains open.

## Explicit non-claims

- WEB APPLICATION ACCEPTED = **NO**
- PILOT estate rows are not invented by the web shell.
- REL-001 release certification is out of scope for this package alone.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial checklist draft (ACCEPTED=NO) |
| 2026-08-09 | WEB-ACCEPT-002: knowledge/graph routes, a11y skip-link, fixture E2E (ACCEPTED=NO) |

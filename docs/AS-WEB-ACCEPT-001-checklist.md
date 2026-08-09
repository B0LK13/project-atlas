# AS-WEB-ACCEPT-001 — Web application acceptance checklist

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-001 through AS-WEB-ACCEPT-004 |
| Parent | D-PROJECT-ATLAS-1.0-MAX-PARALLEL-PLUS-2.0-PREP-001 |
| Tip pin | `c6e6e1d9d1c3e773fc940aae8d45afdd801004c5` / TREE `8fd5279f7da832ae595e8a1f6bc8e1fccaea5b94` (refresh after merge) |
| **WEB APPLICATION ACCEPTED** | **NO** |
| Governor sign-off | **PENDING** — see `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` |

## Normative invariants (ADR-008)

- **UI ≠ canonical**
- **Graph ≠ authority**
- **Unknown ≠ healthy**

## Checklist

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | Production shell routes smoke green (`/`, `/projects`, `/knowledge`, `/graph`, `/ops`, `/command-center`, `/mission-control`, `/workspace`, design-lab) | `apps/web/scripts/smoke.mjs` | automated |
| 2 | Stub + UI enforce UI≠canonical / Graph≠authority / Unknown≠healthy | sample stub + production pages | automated |
| 3 | ADR-008 / ADR-009 / ADR-010 present | smoke + unit tests | automated |
| 4 | `web_api` read-only boundary intact | `web_api/`, tests | automated |
| 5 | Command Center modes present | CommandCenterPage + smoke | automated |
| 6 | Design-lab themes retained | design-lab routes + tokens | automated |
| 7 | Knowledge + Graph production lenses | `/knowledge`, `/graph` + `web_api.knowledge` / `web_api.graph` | automated |
| 8 | a11y skip-link on production shell | `ProdShell` + CSS `:focus` | automated |
| 9 | Fixture E2E read bundle (projects/knowledge/graph/health) | `test_as_web_accept_002_*` | automated |
| 10 | Governor sign-off artifact + tip pin recorded | `docs/AS-WEB-ACCEPT-GOVERNOR-SIGNOFF.md` | **open** |
| 11 | CI / local smoke invocation documented | `apps/web/README.md` | documented |
| 12 | Mission Control + Workspace lenses (route presence only) | `#/mission-control`, `#/workspace` + smoke/unit | automated — **not** WEB ACCEPTED |
| 13 | Ops Health receipt micro-lens (read-only unknown stub) | `#/ops` + smoke/unit | automated — **not** WEB ACCEPTED |

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
| 2026-08-09 | WEB-ACCEPT-003: governor sign-off template + smoke docs; ACCEPTED remains NO |
| 2026-08-09 | Mission Control + Workspace routes noted as automated gates only (ACCEPTED=NO) |
| 2026-08-09 | WEB-ACCEPT-004: refreshed tip pins + Ops Health receipt micro-lens; ACCEPTED remains NO |

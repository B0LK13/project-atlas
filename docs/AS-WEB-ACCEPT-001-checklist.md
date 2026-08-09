# AS-WEB-ACCEPT-001 — Web application acceptance checklist

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-001 |
| Parent | D-PROJECT-ATLAS-1.0-FINISH-PLUS-2.0-PREP-001 |
| Tip pin (draft) | `origin/main` @ governor review |
| **WEB APPLICATION ACCEPTED** | **NO** |
| Governor sign-off | **PENDING** |

This checklist drafts acceptance criteria for the Atlas web application. It does
**not** certify WEB APPLICATION ACCEPTED. Governor checklist green + explicit
sign-off artifact are required before flipping ACCEPTED to YES.

## Normative invariants (ADR-008)

All production web surfaces must preserve:

- **UI ≠ canonical** — browser state never becomes vault truth.
- **Graph ≠ authority** — derived graph / impact lenses never pick authority winners.
- **Unknown ≠ healthy** — absent OBS / read evidence renders unknown, never fabricated healthy.

## Checklist (draft — not certified)

| # | Criterion | Evidence | Status |
|---|---|---|---|
| 1 | Production shell routes smoke green (`/`, `/projects`, `/ops`, `/command-center`, design-lab) | `apps/web/scripts/smoke.mjs` | draft |
| 2 | Stub + UI enforce UI≠canonical / Graph≠authority / Unknown≠healthy | `public/sample-read-status.json`, production pages, `ReadStatusPanel` | draft |
| 3 | ADR-008 / ADR-009 / ADR-010 present and referenced | `docs/adr/ADR-008-*.md`, `ADR-009-*.md`, `ADR-010-*.md`; smoke + unit tests | draft |
| 4 | `web_api` read-only boundary intact — no Core truth writers | `src/project_atlas/web_api/`, `tests/unit/test_as_web_001_web_api.py` | draft |
| 5 | Command Center modes (overview · projects · ops · impact) present | `CommandCenterPage.tsx`, smoke | draft |
| 6 | Design-lab themes retained (AS-WEB-002) without production acceptance claim | design-lab routes + tokens | draft |
| 7 | Governor sign-off artifact + tip pin recorded | evidence package + this doc | **open** |
| 8 | CI smoke invocation documented | `apps/web/README.md`, package scripts | draft |

## Automated gates (non-certifying)

```bash
node apps/web/scripts/smoke.mjs
python -m pytest tests/unit/test_as_web_001_web_api.py tests/unit/test_as_web_accept_001_checklist.py -q
```

Passing automated gates is necessary but **not sufficient** for WEB APPLICATION ACCEPTED.

## Explicit non-claims

- WEB APPLICATION ACCEPTED = **NO**
- PILOT estate rows are not invented by the web shell.
- REL-001 release certification is out of scope for this package alone.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial checklist draft under AS-WEB-ACCEPT-001 (ACCEPTED=NO) |

# AS-WEB-ACCEPT — Governor sign-off package

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-005 governor evidence pack + owner-gates closeout |
| Tip pin (automated evidence) | `8ee65b91871bc04039ffe401a9da3743e4800a8b` / TREE `a2e592a797056935fbec0d8c54033aa3c25a5b06` |
| **WEB APPLICATION ACCEPTED** | **YES** |
| Governor decision | **APPROVED** |
| Directive | `D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001` |

## Purpose

Independent governor review artifact. Automated gates (smoke + unit tests +
typecheck + production build) are necessary. Item 10 is closed by owner
authorization under the directive above after fresh tip verification.

## Automated evidence attached

| # | Criterion | Status |
|---|---|---|
| 1–9 | Routes, invariants, ADRs, web_api RO, CC, design-lab, knowledge/graph, a11y, fixture E2E | automated PASS on tip |
| 11 | CI / local smoke invocation documented in `apps/web/README.md` | documented |
| 10 | This governor sign-off | **closed — APPROVED** |
| 12–13 | Mission Control, Workspace, and Ops Health receipt micro-lens | automated PASS; ACCEPTED follows item 10 |

## Fresh verify (material tip drift from prior pin)

Prior evidence pin `ac1cee7` / TREE `e0ed5478` was superseded by tip
`8ee65b9` / TREE `a2e592a7`. Fresh verify on a clean worktree at that tip:

| Gate | Result |
|---|---|
| Clean WT at tip | PASS |
| `npx tsc -b` | PASS |
| `npm run build` (prod) | PASS |
| `npm run smoke` / `node apps/web/scripts/smoke.mjs` | PASS |
| Focused web acceptance pytest | PASS (43) |
| UI≠canonical / Graph≠authority / Unknown≠healthy | PASS (smoke + page banners) |
| `web_api` read-only / no writer imports | PASS |
| No browser FS write APIs in `apps/web` | PASS (scan empty) |
| CRITICAL / HIGH findings | **0** |

## Governor checklist (human / owner-authorized)

- [x] Reviewed production shell routes live or via smoke transcript
- [x] Confirmed UI≠canonical / Graph≠authority / Unknown≠healthy in UI copy
- [x] Confirmed `web_api` remains read-only (no vault writers)
- [x] Confirmed no invented PILOT estate rows in stubs
- [x] Recorded tip SHA/TREE below after review
- [x] Explicitly authorize `WEB APPLICATION ACCEPTED = YES`

## Sign-off block

```text
GOVERNOR: Owner (directive D-PROJECT-ATLAS-1.0-OWNER-GATES-PARALLEL-CLOSEOUT-001)
DATE: 2026-08-10
TIP: 8ee65b91871bc04039ffe401a9da3743e4800a8b
TREE: a2e592a797056935fbec0d8c54033aa3c25a5b06
DECISION: WEB APPLICATION ACCEPTED = YES
NOTES: Fresh verify after tip drift; APPROVED iff gates matched — they matched.
```

## Explicit claims / non-claims

- WEB APPLICATION ACCEPTED = **YES** (governor APPROVED on pinned tip)
- RELEASE CERTIFIED = **NO** (separate RC gate)
- ESTATE PILOT PASSED (authentic / production estate) = **NO**
- FIXTURE-ONLY CERTIFICATION UNDER OWNER WAIVER = see `docs/AS-PILOT-FIXTURE-ONLY-WAIVER.md`

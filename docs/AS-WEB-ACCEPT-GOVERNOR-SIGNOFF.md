# AS-WEB-ACCEPT — Governor sign-off package (template)

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-004 tip-pin refresh |
| Tip pin (automated evidence) | `c6e6e1d9d1c3e773fc940aae8d45afdd801004c5` / TREE `8fd5279f7da832ae595e8a1f6bc8e1fccaea5b94` (refresh after merge) |
| **WEB APPLICATION ACCEPTED** | **NO** |
| Governor decision | **PENDING** |

## Purpose

Independent governor review artifact. Automated gates (smoke + unit tests)
are **necessary but not sufficient**. This file must be completed by a human
governor before `WEB APPLICATION ACCEPTED` may flip to YES.

## Automated evidence attached

| # | Criterion | Status |
|---|---|---|
| 1–9 | Routes, invariants, ADRs, web_api RO, CC, design-lab, knowledge/graph, a11y, fixture E2E | automated PASS on tip |
| 11 | CI / local smoke invocation documented in `apps/web/README.md` | documented |
| 10 | This governor sign-off | **open** |
| 12–13 | Mission Control, Workspace, and Ops Health receipt micro-lens | automated only; not acceptance |

## Governor checklist (human)

- [ ] Reviewed production shell routes live or via smoke transcript
- [ ] Confirmed UI≠canonical / Graph≠authority / Unknown≠healthy in UI copy
- [ ] Confirmed `web_api` remains read-only (no vault writers)
- [ ] Confirmed no invented PILOT estate rows in stubs
- [ ] Recorded tip SHA/TREE below after review
- [ ] Explicitly authorize `WEB APPLICATION ACCEPTED = YES` (or leave NO)

## Sign-off block (leave blank until review)

```text
GOVERNOR: __________________
DATE: __________________
TIP: __________________
TREE: __________________
DECISION: WEB APPLICATION ACCEPTED = NO | YES
NOTES:
```

## Explicit non-claims until signed

- WEB APPLICATION ACCEPTED = **NO**
- RELEASE CERTIFIED = **NO**
- ESTATE PILOT PASSED = **NO**

# AS-WEB-ACCEPT — Governor sign-off package (template)

| Field | Value |
|---|---|
| Package | AS-WEB-ACCEPT-005 governor evidence pack |
| Tip pin (automated evidence) | `bfdc5862b46c7e8da8fff26224fac8b7b6a2f59f` / TREE `fa404c270c1659d4c48739440a43087a4226b939` |
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

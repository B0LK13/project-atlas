# AS-PROD-ONBOARD-001 — first-run onboarding productization

> **Honesty:** PRODUCTIZATION / **NOT RELEASE** / **NOT PILOT**.
> See [HONESTY.md](./HONESTY.md). Do **not** set `ALPHA_READY=YES` from this package.
> Does **not** implement Core `atlas doctor` (Cloud `#254`). Does **not** add Playwright (`#253`).

| Field | Value |
|---|---|
| Package | `AS-PROD-ONBOARD-001` |
| Audience | Windows **STRANGER** (first local run) |
| Role | Docs + optional thin helper that **links** install → preflight → start → (future) doctor |
| Depends on | `AS-PROD-INSTALL-001` (`docs/productization/install/`, `scripts/windows/atlas-*.ps1`) |
| Optional helper | `scripts/windows/atlas-onboard.ps1` |
| Doctor | Deferred — document the slot only |

## Quick links

- [HONESTY.md](./HONESTY.md) — required honesty banner
- [FIRST-RUN.md](./FIRST-RUN.md) — stranger journey
- [CHECKLIST.md](./CHECKLIST.md) — first-run checklist
- Sibling install: [`../install/STRANGER.md`](../install/STRANGER.md)

## Chain (owned narrative)

```text
clone / checkout
    → install docs + editable pip (AS-PROD-INSTALL-001)
    → atlas-preflight.ps1
    → atlas-start.ps1  (health → browser)
    → (future) atlas doctor   ← NOT in this package (#254)
```

## One action (optional helper)

From the repository root in PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts\windows\atlas-onboard.ps1
```

This only orchestrates existing `atlas-preflight.ps1` and `atlas-start.ps1`. It does not invent estate, does not call doctor, and does not install Playwright.

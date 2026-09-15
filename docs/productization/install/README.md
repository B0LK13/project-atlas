# AS-PROD-INSTALL-001 — productization install docs

> **Honesty banner:** PRODUCTIZATION / **NOT RELEASE** / **NOT PILOT**.
> No MSI, winget, or code signing in this package.
> Local claim only: `STRANGER_CAN_START_ATLAS` after preflight + health.
> Do **not** set `ALPHA_READY=YES` from this path alone.
> Do **not** treat DEMO_FIXTURE success as authentic estate pilot pass.

| Field | Value |
|---|---|
| Package | `AS-PROD-INSTALL-001` |
| Audience | Windows **STRANGER** / OPERATOR |
| TIME_TO_FIRST_VALUE target | ≤ 15 minutes (prepared machine) |
| Primary entry | `scripts/windows/atlas-start.ps1` |
| Preflight | `scripts/windows/atlas-preflight.ps1` |
| Stop | `scripts/windows/atlas-stop.ps1` |
| Runtime | `.tmp/productization/` (disposable; not authentic estate) |

## Quick links

- [STRANGER.md](./STRANGER.md) — one-action stranger path
- [OPERATOR.md](./OPERATOR.md) — operator options, vault modes, limitations
- [LIMITATIONS.md](./LIMITATIONS.md) — honesty + out-of-scope

## Product errors

Failures print structured blocks:

```text
WHAT:   ...
CAUSE:  ...
ACTION: ...
RETRY:  ...
```

See also stderr logs under `.tmp/productization/logs/` when a start was attempted.

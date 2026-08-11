# Limitations — AS-PROD-INSTALL-001

> Honesty banner (required reading):
> **PRODUCTIZATION / NOT RELEASE / NOT PILOT**
> `RELEASE CERTIFIED = NO` · `PILOT PASS = NO` · `PILOT = DORMANT_BLOCKED`
> Local success may support **`STRANGER_CAN_START_ATLAS = YES`** only.

## In scope

- Windows-first stranger bootstrap via PowerShell
- Preflight + editable `pip install -e ".[dev]"`
- DEMO_FIXTURE disposable vault under `.tmp/productization/` **or** explicit existing `-Vault`
- Loopback `atlas live api-serve` + `npm run dev` web shell
- Health checks and browser open
- Structured product errors: WHAT / CAUSE / ACTION / RETRY

## Out of scope (explicit)

- MSI / MSIX installers
- winget publication
- Code signing / SmartScreen reputation
- Authentic estate discovery or inventing pilot roots
- Playwright / browser E2E dependency install (owned elsewhere; do not add here)
- Core `atlas doctor` product matrix (owned by sibling PROD-DOCTOR lane)
- Setting `ALPHA_READY=YES` or release/pilot certificates
- Non-loopback API binds

## Runtime honesty

| Path | Meaning |
|---|---|
| `.tmp/productization/` | Disposable productization runtime |
| DEMO_FIXTURE estate | Fixture corpus only — not authentic estate |
| Operator `-Vault` | Caller-supplied existing vault — still NOT RELEASE / NOT PILOT by itself |

## Related stranger docs

- [STRANGER.md](./STRANGER.md)
- [OPERATOR.md](./OPERATOR.md)
- [README.md](./README.md)

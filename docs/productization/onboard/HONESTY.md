# Honesty banner — AS-PROD-ONBOARD-001

> **PRODUCTIZATION / NOT RELEASE / NOT PILOT**
>
> `RELEASE CERTIFIED = NO`  
> `PILOT PASS = NO`  
> `PILOT = DORMANT_BLOCKED`  
> `ALPHA_READY = NO` (do **not** flip from this package)

## What this package claims

| Claim | Status |
|---|---|
| First-run docs link install → preflight → start | YES (this package) |
| Optional thin Windows orchestrator (`atlas-onboard.ps1`) | YES (calls existing install scripts only) |
| `STRANGER_CAN_START_ATLAS` | Owned by install lane (`AS-PROD-INSTALL-001`) after healthy start — not re-certified here |
| `atlas doctor` / Core doctor CLI | **NOT IMPLEMENTED HERE** — owned by Cloud `#254` / PROD-DOCTOR |
| Playwright / web E2E | **OUT OF SCOPE** — owned elsewhere (`#253`) |
| MSI / winget / code signing | **OUT OF SCOPE** |
| Authentic estate pilot pass | **NO** |

## Required reading before first run

1. This honesty banner
2. Sibling install honesty: [`../install/README.md`](../install/README.md)
3. First-run journey: [`FIRST-RUN.md`](./FIRST-RUN.md)

## Forbidden stamps

Do not emit or imply release certification, pilot pass, or alpha-ready success
from this package. Keep these stamps negative:

- `RELEASE CERTIFIED = NO`
- `PILOT PASS = NO`
- `ALPHA_READY = NO`
- Do not claim “doctor is ready” until `#254` lands Core doctor

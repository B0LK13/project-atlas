# Architecture — isolated demo browser-E2E

## Problem

`apps/web` ships Node smoke (`scripts/smoke.mjs`) and Vite build gates.
There is **no** repo-standard Playwright/Cypress suite for Mission/Workspace
chip walkthroughs. External browser MCP tooling may also fail (tab create/vanish).

## Isolated package meaning

"Isolated" means:

1. Lives under `docs/demo/browser-e2e/` (demo surface only)
2. Does **not** mutate Core runtime or `apps/web` production code
3. Does **not** pull browser-automation dependencies into the install matrix
4. Provides a durable recording surface for `BROWSER_E2E_MISSING`

## Recording flow

```
demo-up Path A (optional) → attempt chip walkthrough / automation
        │
        ├─ success → record Path A/B observed (separate receipt)
        │
        └─ harness missing / tooling blocked
                 → emit BROWSER_E2E_MISSING receipt (this package)
                 → charter alternative path may apply IFF other DEMO gates PASS
```

## Fail-closed

- Screenshot-only certification is **not** sufficient (FRONTEND-SUITE)
- Missing harness ≠ invent Path A chips observed
- This package ≠ release cert / ≠ PILOT

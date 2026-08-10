# Browser E2E — architecture (isolated harness)

Package: **AS-DEMO-2.1-BROWSER-E2E-001**

Status: **HARNESS ISOLATION / DOCS + FIXTURES ONLY**. No in-repo Playwright or
Cypress runner. No mutation of `apps/web`.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
AUTHENTIC PILOT PASS = NO
TECHNICAL DEMO — VERIFIED = NOT stamped by this package alone
```

## Why the repository has no Playwright / Cypress suite

As of tip `d994953` (and the AS-DEMO-2.1-001 harvest wave):

1. **`apps/web` verification bar** is Node smoke (`scripts/smoke.mjs`) plus
   build, plus docs-driven Path A/B chip walkthroughs in
   [`../FRONTEND-SUITE.md`](../FRONTEND-SUITE.md).
2. **No package.json browser-driver dependency** ships for the production shell
   (no Playwright, no Cypress). Adding one under a demo docs package would
   expand the production surface beyond TECHNICAL_PREVIEW harness isolation.
3. **Browser MCP automation failed** in coordinator evidence
   (`D:\project-atlas-orphans\atlas-2.1-productionization-001\`): tab create
   issued a viewId then immediately vanished; navigate against localhost failed.
   That is a tooling blocker, not a silent PASS.
4. Charter explicitly allows recording **`BROWSER_E2E_MISSING`** when an
   **isolated** demo-E2E package lands — this tree is that package.

Intentional absence is therefore an honesty choice: do not pretend a repo E2E
driver exists, and do not invent chip observations to close the certificate.

## What “isolated” means

```text
Layer A — apps/web runtime (untouched by this package)
  Vite + React hash router
  Node smoke / build gates
  Manual Path A / Path B walkthroughs (FRONTEND-SUITE)

Layer B — Isolated demo browser-E2E package (this tree)
  Architecture + contract + invariants
  BROWSER_E2E_MISSING receipt fixture
  Negative fail-closed expects
  Operator checklist

Layer C — Forbidden on this tip under this package
  Playwright/Cypress install
  CI browser job invent
  Auto VERIFIED stamp
```

Isolation boundaries:

| Boundary | Rule |
|---|---|
| Source | Only `docs/demo/browser-e2e/**` (+ unique unit test); minimal index links |
| Runtime | Do not edit `apps/web/**` |
| Deps | Do not add browser-driver packages |
| Evidence class | `DEMO_FIXTURE` / harness receipt — **NOT RELEASE EVIDENCE** |
| Authority | UI chips remain non-canonical; graph ≠ authority |

## How operators record `BROWSER_E2E_MISSING`

1. Confirm no repo Playwright/Cypress harness on the tip under test.
2. Attempt (or document prior attempt of) Path A/B chip walkthrough per
   FRONTEND-SUITE **or** document tooling blocker that prevents observation
   (e.g. browser MCP unavailable).
3. Fill [`checklists/browser-e2e.md`](checklists/browser-e2e.md).
4. Emit a receipt shaped like
   [`fixtures/browser-e2e-missing.receipt.sample.json`](fixtures/browser-e2e-missing.receipt.sample.json):
   - `status: "BROWSER_E2E_MISSING"`
   - `path_a_chips_observed: false` unless a **separate** observation receipt
     proves otherwise
   - `release_certified: false`
   - `pilot_pass: false`
   - tooling_blocker notes populated
5. File the receipt under the coordinator/orphan evidence root (not as a claim
   that VERIFIED is automatic).

### Allowed status vocabulary

| Status | Meaning |
|---|---|
| `BROWSER_E2E_PASS` | Reserved for a future real harness or verified human chip walkthrough receipt — **not** claimed by landing this package |
| `BROWSER_E2E_MISSING` | Harness absent / tooling blocked; isolation package recorded |
| `BROWSER_E2E_FAIL` | Attempted observation failed with evidence (not silent invent) |

This package’s sample fixture uses **`BROWSER_E2E_MISSING` only**.

## Relationship to other demo gates

```text
Clean-clone / backend suite
  + frontend smoke + build
  + live API smoke
  + MCP consistency
  + ADV demo certify
  + full pytest
  + (browser E2E PASS  OR  BROWSER_E2E_MISSING + this package)
        │
        ▼
  Coordinator may consider TECHNICAL DEMO — VERIFIED
        │
        ├── still NOT RELEASE CERTIFIED
        └── still NOT AUTHENTIC PILOT PASS
```

Missing any non-browser gate cannot be repaired by this package.

## Explicit non-claims

- Not a Playwright/Cypress implementation
- Not Path A chip observation invent
- Not `TECHNICAL DEMO — VERIFIED` already earned
- Not `ATLAS_2_1_RELEASE_CERTIFIED = YES`
- Not authentic estate PILOT PASS
- Not a substitute for `npm run smoke` / `npm run build`

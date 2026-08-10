# AS-DEMO-2.1-BROWSER-E2E-001 — Isolated demo browser-E2E package

| Field | Value |
|---|---|
| Package | **AS-DEMO-2.1-BROWSER-E2E-001** |
| Class | `TECHNICAL_PREVIEW` / `HARNESS_ISOLATION` / `NON_RELEASE_CERTIFICATION` |
| Parent charter | [`../AS-DEMO-2.1-001.md`](../AS-DEMO-2.1-001.md) |
| Sibling runbook | [`../FRONTEND-SUITE.md`](../FRONTEND-SUITE.md) (D05) |
| Scope | `docs/demo/browser-e2e/**` (+ unique unit test) |
| Production mutation | **NONE** (`apps/web`, Playwright/Cypress deps forbidden) |
| Certificate target | Enables charter **alternative** path only — does **not** auto-stamp VERIFIED |
| Release claim | **NOT RELEASE CERTIFIED** |
| Pilot claim | **NOT AUTHENTIC PILOT PASS** · PILOT DORMANT |
| Tip audited | `d9949530ca023647c6e6c9c76e3ba6864265e8c7` |

## Purpose

Formalize the charter-allowed honesty path when repository browser automation
is unavailable:

```text
browser/demo E2E passes
  OR
BROWSER_E2E_MISSING is recorded AND an isolated demo-E2E package lands
```

Tip `main` ships Node smoke (`apps/web/scripts/smoke.mjs`) and frontend docs,
but **no** Playwright/Cypress harness. Operator browser MCP automation against
localhost failed (tab create → vanish / navigate fail). This package is the
honest, isolated documentation + fixture harness that records
`BROWSER_E2E_MISSING` without inventing Path A chip observations or flipping
**TECHNICAL DEMO — VERIFIED** by stub alone.

## Why “isolated”

| Meaning | This package |
|---|---|
| Docs-owned under `docs/demo/browser-e2e/` | Yes |
| No `apps/web` runtime mutation | Yes |
| No Playwright / Cypress dependency added | Yes |
| Receipts are DEMO / fixture class only | Yes |
| Auto-certifies TECHNICAL DEMO — VERIFIED | **No** |
| Substitutes for pipeline / API / MCP / ADV / pytest / frontend smoke | **No** |

“Isolated” means the harness lives beside the demo charter as a **recording and
fail-closed contract surface**, not as an in-repo browser driver that claims
chip walkthrough success.

## Relation to FRONTEND-SUITE / charter

| Surface | Role vs this package |
|---|---|
| `AS-DEMO-2.1-001` charter | Normative VERIFIED envelope; lists `BROWSER_E2E_MISSING` + isolated package as alternative to live browser/demo E2E |
| `FRONTEND-SUITE.md` | Operator Path A/B chip walkthrough + smoke/build; records `BROWSER_E2E_MISSING` when no harness |
| `checklists/frontend.md` | Manual frontend honesty checklist (still required for chip observation when claimed) |
| **This package** | Formal receipt schema, negative fixtures, operator checklist for recording the missing harness — enables the charter alternative path |

Landing this package satisfies the **documentation / harness-isolation** half of
the charter alternative. It does **not** invent Path A chip observation and
does **not** by itself set **TECHNICAL DEMO — VERIFIED**.

## Deliverables

| Path | Role |
|---|---|
| [`ARCHITECTURE.md`](ARCHITECTURE.md) | Why no repo Playwright/Cypress; isolation; how to record `BROWSER_E2E_MISSING` |
| [`CONTRACT.md`](CONTRACT.md) | Receipt fields + fail-closed operations |
| [`INVARIANTS.md`](INVARIANTS.md) | Hard honesty rules |
| [`FIXTURE-PLAN.md`](FIXTURE-PLAN.md) | Fixture family inventory |
| [`fixtures/`](fixtures/) | Sample missing receipt + negative expects |
| [`checklists/browser-e2e.md`](checklists/browser-e2e.md) | Operator checklist |

## Hard non-claims (package card)

- **TECHNICAL DEMO — VERIFIED** is **not** already earned by this package landing
- **NOT RELEASE CERTIFIED** — never set `ATLAS_2_1_RELEASE_CERTIFIED`
- **NOT AUTHENTIC PILOT PASS** — never invent PILOT / authentic estate
- `path_a_chips_observed: false` in the sample missing receipt — do not invent true
- HTTP 200 on demo-up Path A ≠ chip walkthrough ≠ VERIFIED
- Frontend `npm run smoke` / `npm run build` PASS ≠ browser E2E PASS

## Forbidden

- Adding Playwright, Cypress, or other browser-driver deps to the repo
- Mutating `apps/web` source under this package ID
- Claiming Path A / Path B chip observation without an operator receipt that
  actually records those observations
- Gaming VERIFIED via an empty stub that only prints `BROWSER_E2E_MISSING`
- Setting release or pilot flags from demo receipts

## Exit (this package)

Complete when this tree lands via PR with substantive docs, fixtures, checklist,
cross-links from FRONTEND-SUITE / README / LIMITATIONS, and a unit honesty test.
Unlock / release / pilot remain **NO**. Charter VERIFIED remains an independent
operator/coordinator judgment after **all** required gates (pipeline, API, MCP,
ADV, pytest, frontend smoke, **and** either live browser E2E **or** this
recorded missing path plus remaining gate evidence).

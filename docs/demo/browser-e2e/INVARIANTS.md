# Browser E2E — invariants (isolated harness)

Status: **HARNESS ISOLATION**. These rules freeze the fail-closed honesty posture
for `AS-DEMO-2.1-BROWSER-E2E-001`.

## Certification posture

```text
ATLAS_2_1_RELEASE_CERTIFIED = NO
AUTHENTIC PILOT PASS = NO
TECHNICAL DEMO — VERIFIED ≠ this package alone
```

## Hard invariants

| ID | Rule | Shorthand |
|---|---|---|
| AS-BROWSER-E2E-INV-MISSING-001 | When no repo driver exists, status must be `BROWSER_E2E_MISSING` (or FAIL with evidence) — never silent PASS | **NO SILENT PASS** |
| AS-BROWSER-E2E-INV-PATH-A-001 | Must not invent Path A chip observation (`path_a_chips_observed` stays false without evidence) | **NO PATH-A INVENT** |
| AS-BROWSER-E2E-INV-VERIFIED-001 | Package alone does not stamp **TECHNICAL DEMO — VERIFIED** | **PACKAGE ≠ VERIFIED** |
| AS-BROWSER-E2E-INV-GATES-001 | Pipeline / API / MCP / ADV / pytest / frontend smoke remain independent required gates | **OTHER GATES STILL REQUIRED** |
| AS-BROWSER-E2E-INV-RELEASE-001 | `release_certified` / `atlas_2_1_release_certified` remain false | **NOT RELEASE CERTIFIED** |
| AS-BROWSER-E2E-INV-PILOT-001 | `pilot_pass` remains false; no authentic estate invent | **NOT AUTHENTIC PILOT PASS** |
| AS-BROWSER-E2E-INV-RUNTIME-001 | No Playwright/Cypress deps; no `apps/web` mutation under this package | **NO DRIVER / NO WEB MUTATION** |
| AS-BROWSER-E2E-INV-HTTP-001 | demo-up Path A HTTP 200 ≠ chip walkthrough ≠ VERIFIED | **HTTP ≠ CHIPS** |

## Negative outcomes (expected fail-closed)

| Attempt | Expected error key |
|---|---|
| Claim VERIFIED from this package alone | `browser-e2e-invent-verified-forbidden` |
| Invent Path A chips observed | `browser-e2e-invent-path-a-observed-forbidden` |
| Claim RELEASE CERTIFIED from demo harness | `browser-e2e-release-certified-forbidden` |

## Allowed documentation posture

- Record tooling blockers honestly (browser MCP unavailable, no repo harness)
- Link FRONTEND-SUITE Path A/B as the manual observation path when chips are claimed
- Keep all new harness files under `docs/demo/browser-e2e/**` (+ unique unit test)
- Minimal cross-links from `FRONTEND-SUITE.md`, `README.md`, `LIMITATIONS.md`

## Forbidden documentation posture

- Stating **TECHNICAL DEMO — VERIFIED** as already earned by this package
- Setting `ATLAS_2_1_RELEASE_CERTIFIED` or inventing PILOT PASS
- Empty one-file stub whose only purpose is to flip the charter checkbox
- Relabeling smoke/build/HTTP success as browser E2E PASS

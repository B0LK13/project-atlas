# Browser E2E — contract (isolated harness)

Package: **AS-DEMO-2.1-BROWSER-E2E-001**

Status: **docs-owned contract + fixtures only**. No runtime CLI/MCP surface.
Not promoted to `src/project_atlas/schemas/`.

## Honesty envelope

```text
DEMO
NOT AUTHENTIC PILOT
NOT RELEASE EVIDENCE
BROWSER_E2E_MISSING
NOT RELEASE CERTIFIED
NOT AUTHENTIC PILOT PASS
```

Landing this package **enables** the charter alternative path. It does **not**
auto-verify **TECHNICAL DEMO — VERIFIED**.

## Receipt contract (sample fields)

Canonical sample:
[`fixtures/browser-e2e-missing.receipt.sample.json`](fixtures/browser-e2e-missing.receipt.sample.json)

| Field | Type | Required posture on missing receipt |
|---|---|---|
| `package_id` | string | `AS-DEMO-2.1-BROWSER-E2E-001` |
| `status` | string | `BROWSER_E2E_MISSING` |
| `path_a_chips_observed` | boolean | `false` unless separate observation proves true |
| `path_b_chips_observed` | boolean | `false` unless separate observation proves true |
| `release_certified` | boolean | **must be `false`** |
| `pilot_pass` | boolean | **must be `false`** |
| `technical_demo_verified` | boolean | **must be `false`** on this package’s sample |
| `atlas_2_1_release_certified` | boolean | **must be `false`** |
| `evidence_class` | string | `DEMO_FIXTURE` / harness-isolation |
| `tooling_blocker` | object | notes on why browser automation is missing |
| `non_claims` | string[] | explicit NOT RELEASE / NOT PILOT / ≠ VERIFIED alone |

## Requirement traceability

| ID | Requirement |
|---|---|
| FR-BROWSER-E2E-001 | Operators may record `BROWSER_E2E_MISSING` when no repo harness exists |
| FR-BROWSER-E2E-002 | Missing receipt must keep `path_a_chips_observed: false` unless observation evidence exists |
| FR-BROWSER-E2E-003 | Package landing alone must not set `technical_demo_verified: true` |
| NFR-BROWSER-E2E-001 | No Playwright/Cypress deps introduced by this package |
| NFR-BROWSER-E2E-002 | Deterministic fixture JSON (`sort_keys` friendly; no wall-clock invent in samples) |
| AT-BROWSER-E2E-001 | Negative fixture rejects inventing VERIFIED from this package alone |
| AT-BROWSER-E2E-002 | Negative fixture rejects inventing Path A chip observation |
| AT-BROWSER-E2E-003 | Negative fixture rejects release-certified invent |

## Operations (documentary — not implemented runtime)

| Operation | Input | Output | Fail closed when |
|---|---|---|---|
| `browser-e2e.missing.record` | Tip SHA + tooling notes | `BROWSER_E2E_MISSING` receipt | Attempt claims chips observed without evidence |
| `browser-e2e.verified.claim` | Full demo gate set | Coordinator VERIFIED judgment | Claimed from this package alone |
| `browser-e2e.release.claim` | — | Forbidden | Any release stamp from demo harness |
| `browser-e2e.pilot.claim` | — | Forbidden | Any authentic pilot invent |

## Fail-closed matrix

| Attempt | Expected error key |
|---|---|
| Claim VERIFIED from this package alone | `browser-e2e-invent-verified-forbidden` |
| Set `path_a_chips_observed: true` without observation receipt | `browser-e2e-invent-path-a-observed-forbidden` |
| Set `release_certified: true` / `ATLAS_2_1_RELEASE_CERTIFIED` | `browser-e2e-release-certified-forbidden` |
| Add Playwright/Cypress under this package | `browser-e2e-driver-dep-forbidden` |

Negative fixtures:

- [`fixtures/negative-invent-verified.expect.json`](fixtures/negative-invent-verified.expect.json)
- [`fixtures/negative-invent-path-a-observed.expect.json`](fixtures/negative-invent-path-a-observed.expect.json)
- [`fixtures/negative-release-certified.expect.json`](fixtures/negative-release-certified.expect.json)

## Non-claims

- Contract stubs are not package data on this tip
- Operations are not CLI/MCP surfaces on this tip
- Sample missing receipt ≠ TECHNICAL DEMO — VERIFIED
- Sample missing receipt ≠ RELEASE CERTIFIED
- Sample missing receipt ≠ AUTHENTIC PILOT PASS

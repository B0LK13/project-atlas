# Browser E2E — fixture plan (isolated harness)

Package: `AS-DEMO-2.1-BROWSER-E2E-001`.

## Fixture families

| Family | File(s) | Role |
|---|---|---|
| Missing receipt sample | `browser-e2e-missing.receipt.sample.json` | Canonical `BROWSER_E2E_MISSING` receipt shape |
| Negative — VERIFIED invent | `negative-invent-verified.expect.json` | Fail closed if package alone claims VERIFIED |
| Negative — Path A invent | `negative-invent-path-a-observed.expect.json` | Fail closed if chips observed invented |
| Negative — release invent | `negative-release-certified.expect.json` | Fail closed if release certified invented |

## Scenario rows

| scenario_id | Intent | Expected |
|---|---|---|
| FX-DEMO-BROWSER-E2E-001 | Record missing harness on tip without driver | `status=BROWSER_E2E_MISSING`, chips false, release/pilot false |
| FX-DEMO-BROWSER-E2E-NEG-001 | Reject VERIFIED invent from package alone | `browser-e2e-invent-verified-forbidden` |
| FX-DEMO-BROWSER-E2E-NEG-002 | Reject Path A observation invent | `browser-e2e-invent-path-a-observed-forbidden` |
| FX-DEMO-BROWSER-E2E-NEG-003 | Reject release-certified invent | `browser-e2e-release-certified-forbidden` |

## Constraints

- All fixtures: `evidence_class` demo/fixture/harness — **NOT RELEASE EVIDENCE**
- All fixtures: `release_certified = false`, `pilot_pass = false`
- Sample missing receipt: `technical_demo_verified = false`
- Sample missing receipt: `path_a_chips_observed = false`
- Do **not** invent wall-clock “pass timestamps” that imply live browser success
- Do **not** add Playwright/Cypress payloads or CI job stubs that claim PASS

## Validation (post-land)

```bash
python -m pytest tests/unit/test_as_demo_2_1_browser_e2e_001.py -q
```

## Evidence root (operators)

Coordinator / orphan evidence (outside repo):

`D:\project-atlas-orphans\atlas-2.1-productionization-001\`

Copy filled receipts there; do not treat this package’s sample JSON as a live
run receipt for VERIFIED.

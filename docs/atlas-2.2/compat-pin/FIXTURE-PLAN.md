# Compatibility pin — fixture plan (PREP)

Package: `AS-2.2-COMPAT-PIN-PREP-001`.

## Fixture families

| Family | File(s) | Role |
|---|---|---|
| Expectation inventory | `compat-expectation.fixture.json` | Anchor succession + consumer rows |
| Negative — release cert invent | `negative-release-certified.expect.json` | Fail closed on 2.1 cert claim |
| Negative — PILOT invent | `negative-pilot-invent.expect.json` | Fail closed on PILOT root invent |
| Deepen forbidden-action | `compat-pin-forbidden-action.schema.json` | Enum fail-closed vocabulary (PREP stub) |
| Deepen negatives | `negative-deepen-*.expect.json` | FX-2.2-COMPAT-DEEPEN-101..105 |

## Deepen negatives (AS-2.2-COMPAT-PIN-DEEPEN-PREP-001)

| ID | File | kind |
|---|---|---|
| FX-2.2-COMPAT-DEEPEN-101 | `negative-deepen-release-cert-stamp.expect.json` | `release_cert_stamp` |
| FX-2.2-COMPAT-DEEPEN-102 | `negative-deepen-pilot-invent.expect.json` | `pilot_invent` |
| FX-2.2-COMPAT-DEEPEN-103 | `negative-deepen-anchor-publish.expect.json` | `anchor_publish` |
| FX-2.2-COMPAT-DEEPEN-104 | `negative-deepen-runtime-mutation.expect.json` | `runtime_mutation` |
| FX-2.2-COMPAT-DEEPEN-105 | `negative-deepen-future-pin-as-live.expect.json` | `future_pin_as_live` |

All deepen negatives: `evidence_class=fixture-only`, `authentic_estate=false`,
`release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.

## Scenario rows (expectation inventory)

| scenario_id | consumer_package | anchor | status |
|---|---|---|---|
| FX-2.2-COMPAT-001 | AS-2.0-COMPAT-001 | atlas-1.0.0-compat | certified-reference |
| FX-2.2-COMPAT-002 | AS-2.2-COMPAT-PIN-001 | atlas-2.1.0-compat | future-placeholder |
| FX-2.2-COMPAT-003 | AS-2.2-KCI-001 | atlas-2.1.0-compat | declared-dependency |
| FX-2.2-COMPAT-004 | AS-2.2-RET-CTX-001 | atlas-2.1.0-compat | declared-dependency |
| FX-2.2-COMPAT-005 | AS-2.2-CTX-COMPILER-001 | atlas-2.1.0-compat | declared-dependency |

## Constraints

- All fixtures: `evidence_class = fixture-only`, `authentic_estate = false`
- All fixtures: `atlas_2_1_release_certified = false`, `pilot_roots = 0`
- Do **not** create `docs/releases/2.1.0/` payloads until post-cert unlock
- Do **not** promote schemas to package data on this tip

## Validation (post-land)

```bash
python -m pytest tests/unit/test_as_2_2_compat_pin_prep_001.py tests/unit/test_as_2_2_compat_pin_deepen_prep_001.py -q
```

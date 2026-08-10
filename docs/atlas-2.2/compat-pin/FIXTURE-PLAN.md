# Compatibility pin — fixture plan (PREP)

Package: `AS-2.2-COMPAT-PIN-PREP-001`.

## Fixture families

| Family | File(s) | Role |
|---|---|---|
| Expectation inventory | `compat-expectation.fixture.json` | Anchor succession + consumer rows |
| Negative — release cert invent | `negative-release-certified.expect.json` | Fail closed on 2.1 cert claim |
| Negative — PILOT invent | `negative-pilot-invent.expect.json` | Fail closed on PILOT root invent |

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
python -m pytest tests/unit/test_as_2_2_compat_pin_prep_001.py -q
```

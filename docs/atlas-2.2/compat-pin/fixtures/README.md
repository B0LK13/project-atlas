# Compatibility pin — fixtures (PREP)

Package: **AS-2.2-COMPAT-PIN-PREP-001**

Synthetic rehearsal payloads only. `evidence_class = fixture-only`.

| File | Role |
|---|---|
| `compat-expectation.fixture.json` | Anchor succession + consumer dependency rows |
| `negative-release-certified.expect.json` | Forbidden 2.1 release-cert invent |
| `negative-pilot-invent.expect.json` | Forbidden PILOT root invent |

All fixtures set `atlas_2_1_release_certified: false` and `pilot_roots: 0`.

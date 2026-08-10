# Fixture plan (PREP) — roadmap crosswalk deepen

Package: **AS-2.2-ROADMAP-CROSSWALK-DEEPEN-PREP-001**

Base positive/stub fixture (`crosswalk.fixture.json`) remains owned by
`AS-2.2-ROADMAP-CROSSWALK-PREP-001` — do not relocate.

| Fixture | Role |
|---|---|
| `negative-deepen-unlock-claim.expect.json` | Reject unlock claim from mapping row |
| `negative-deepen-production-ready-claim.expect.json` | Reject production-ready claim |
| `negative-deepen-release-cert-stamp.expect.json` | Reject release-cert stamp |
| `negative-deepen-pilot-invent.expect.json` | Reject pilot invent |
| `negative-deepen-runtime-mutation.expect.json` | Reject runtime / apps mutation |
| `negative-deepen-llm-authority.expect.json` | Reject LLM authority stamp |
| `negative-deepen-fixture-as-certification.expect.json` | Reject fixture-as-certification |

All deepen negatives: `status=rejected_forbidden`,
`evidence_class=fixture-only`, `authentic_estate=false`,
`release_certified=false`, `pilot_pass=false`, `canonical_writes=false`.

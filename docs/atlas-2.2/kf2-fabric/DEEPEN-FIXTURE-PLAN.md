# Fixture plan (PREP) — KF2 fabric deepen

Package: **AS-2.2-KF2-FABRIC-DEEPEN-PREP-001**  
Status: **PREP ONLY**. Payloads under `docs/atlas-2.2/kf2-fabric/fixtures/`
named `negative-deepen-*` validate against
`kf2-fabric-forbidden-action.schema.json`.

Base FX-2.2-KF2-001..008 remain on existing paths — **do not relocate**.
Deepen forbidden-action negatives are additive.

| ID | Fixture | Role |
|---|---|---|
| FX-2.2-KF2-DEEPEN-101 | `negative-deepen-authority-elevate.expect.json` | Reject authority elevation |
| FX-2.2-KF2-DEEPEN-102 | `negative-deepen-cross-promote.expect.json` | Reject cross-promote |
| FX-2.2-KF2-DEEPEN-103 | `negative-deepen-projection-write.expect.json` | Reject projection write |
| FX-2.2-KF2-DEEPEN-104 | `negative-deepen-layer-b-write.expect.json` | Reject Layer B write |
| FX-2.2-KF2-DEEPEN-105 | `negative-deepen-release-cert-stamp.expect.json` | Reject release-cert stamp |
| FX-2.2-KF2-DEEPEN-106 | `negative-deepen-pilot-invent.expect.json` | Reject pilot invent |
| FX-2.2-KF2-DEEPEN-107 | `negative-deepen-llm-authority.expect.json` | Reject LLM authority |
| FX-2.2-KF2-DEEPEN-108 | `negative-deepen-kf2-runtime-mutation.expect.json` | Reject KF2 runtime mutation |

All deepen negatives: `evidence_class=fixture-only`, `authentic_estate=false`,
`release_certified=false`, `pilot_pass=false`, `canonical_writes=false`,
`status=rejected_forbidden`. **Gate credit: NO.**

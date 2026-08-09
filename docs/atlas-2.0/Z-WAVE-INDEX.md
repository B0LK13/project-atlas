# Atlas 2.0 — Z-wave prep index

Status: **PREP ONLY** — `ATLAS_2_0_IMPLEMENTATION_READY = NO`.

Idle Track B lanes for deepening `docs/atlas-2.0/**` without production
semantics or dependency-bearing 2.0 schemas. Every lane stays `READY=NO`
until a governor flips the IMPLEMENTATION READY gate after 1.0 freeze.

## Prep lanes Z1–Z14

| ID | Theme | Status | READY |
|---|---|---|---|
| Z1 | Charter & purpose envelope | PREP | NO |
| Z2 | Vision themes (non-normative) | PREP | NO |
| Z3 | PRD / FR catalog seed | PREP | NO |
| Z4 | Dependency DAG & entry gates | PREP | NO |
| Z5 | Threat model register | PREP | NO |
| Z6 | Federation package contracts (FED) | PREP | NO |
| Z7 | UX / Command Center contracts | PREP | NO |
| Z8 | Provider adapter contracts (PROV) | PREP | NO |
| Z9 | Estate sync v2 contracts (SYNC) | PREP | NO |
| Z10 | Compatibility snapshot consumer | PREP | NO |
| Z11 | Fixture families & harness policy | PREP | NO |
| Z12 | OpenAI / MCP design sketches | PREP | NO |
| Z13 | Open questions & research blockers | PREP | NO |
| Z14 | Prototype markers & READY firewall | PREP | NO |

## Cross-links (prep artifacts)

| Lane | Primary artifact(s) |
|---|---|
| Z1 | [CHARTER.md](CHARTER.md) |
| Z2 | [VISION.md](VISION.md) |
| Z3 | [PRD.md](PRD.md), [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md) |
| Z4 | [DAG.md](DAG.md) |
| Z5 | [THREAT-MODEL.md](THREAT-MODEL.md) |
| Z6–Z10 | [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md), [COMPATIBILITY.md](COMPATIBILITY.md) |
| Z11 | [FIXTURE-PLAN.md](FIXTURE-PLAN.md), [fixtures/README.md](fixtures/README.md) |
| Z12 | [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md) |
| Z13 | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |
| Z14 | [PROTOTYPE-MARKERS.md](PROTOTYPE-MARKERS.md) |

## Firewall

- Docs-only: no `src/` production semantics from these lanes.
- No dependency-bearing 2.0 schemas shipped as package data.
- Do **not** claim `ATLAS_2_0_IMPLEMENTATION_READY = YES` from this index.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial Z1–Z14 prep lane map (`READY=NO`) |

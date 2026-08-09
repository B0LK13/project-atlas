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

## Status notes (deepen-f / PREP)

All notes below are Track B progress only. None flip READY.

| ID | Prep status note |
|---|---|
| Z1 | CHARTER.md present as PROTOTYPE purpose envelope; not certified. |
| Z2 | VISION.md themes drafted; explicitly non-normative. |
| Z3 | PRD.md + PACKAGE-CONTRACT-STUBS FR-2.0-xxx seed; placeholders only. |
| Z4 | DAG.md carries observed prep tip; certified 1.0 snapshot pin still pending RELEASE CERTIFIED. |
| Z5 | THREAT-MODEL.md register T-2.0-001…020; mitigations = design intent. |
| Z6 | AS-2.0-FED-001 stubs + OQ-001…003 + OQ-016 open; no join schema shipped. |
| Z7 | AS-2.0-UX-001 stubs blocked on WEB APPLICATION ACCEPTED = NO; false-stamp question OQ-017 open. |
| Z8 | AS-2.0-PROV-001 stubs + OPENAI-MCP-DESIGN PROTOTYPE; no SDK wiring. |
| Z9 | AS-2.0-SYNC-001 stubs; tombstone/conflict/queue authorization unresolved (OQ-011/012/018). |
| Z10 | COMPATIBILITY.md snapshot pin model sketched; consumer not frozen. |
| Z11 | FIXTURE-PLAN.md + fixtures/README scenario/evidence-class inventory; no payload harness. |
| Z12 | OPENAI-MCP-DESIGN.md marked PROTOTYPE; production wiring forbidden. |
| Z13 | OPEN-QUESTIONS.md OQ-001…019 unanswered; research blockers intact. |
| Z14 | PROTOTYPE-MARKERS.md + `prototypes/` stub; READY firewall explicit NO. |

## Deepen-f delta (no readiness credit)

- Contract checklist now carries per-stub FR/INV/schema review sketches; all
  review and freeze cells remain unchecked / NO.
- Package boundaries now state candidate IN/OUT/FORBIDDEN surfaces without APIs
  or shipped schemas.
- Threat inventory reaches T-2.0-020 and fixture scenarios include mandatory
  negative cases and evidence-class separation.
- The observed prep tip is pinned in DAG/gate artifacts but is explicitly not a
  certified compatibility snapshot.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Cross-links (prep artifacts)

| Lane | Primary artifact(s) |
|---|---|
| Z1 | [CHARTER.md](CHARTER.md) |
| Z2 | [VISION.md](VISION.md) |
| Z3 | [PRD.md](PRD.md), [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md) |
| Z4 | [DAG.md](DAG.md) |
| Z5 | [THREAT-MODEL.md](THREAT-MODEL.md) |
| Z6–Z10 | [PACKAGE-CONTRACT-STUBS.md](PACKAGE-CONTRACT-STUBS.md), [COMPATIBILITY.md](COMPATIBILITY.md), [CONTRACT-FREEZE-CHECKLIST.md](CONTRACT-FREEZE-CHECKLIST.md) |
| Z11 | [FIXTURE-PLAN.md](FIXTURE-PLAN.md), [fixtures/README.md](fixtures/README.md) |
| Z12 | [OPENAI-MCP-DESIGN.md](OPENAI-MCP-DESIGN.md) |
| Z13 | [OPEN-QUESTIONS.md](OPEN-QUESTIONS.md) |
| Z14 | [PROTOTYPE-MARKERS.md](PROTOTYPE-MARKERS.md), [prototypes/README.md](prototypes/README.md), [IMPLEMENTATION-READY-GATE.md](IMPLEMENTATION-READY-GATE.md) |

## Firewall

- Docs-only: no `src/` production semantics from these lanes.
- No dependency-bearing 2.0 schemas shipped as package data.
- Do **not** claim `ATLAS_2_0_IMPLEMENTATION_READY = YES` from this index.

## Changelog

| Date | Change |
|---|---|
| 2026-08-09 | Initial Z1–Z14 prep lane map (`READY=NO`) |
| 2026-08-09 | deepen-e: per-lane status notes; contract-freeze + prototypes cross-links |
| 2026-08-09 | deepen-f: deeper contract boundaries, threats, fixture scenarios, blockers, and non-certified tip pin; READY=NO |

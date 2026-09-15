# Atlas 2.0 — Z-wave prep index

Status: `ATLAS_2_0_IMPLEMENTATION_READY = YES` after AS-REL-001
(certified 1.0 anchor `f407981` / `feb0441a` / `v1.0.0`). Historical deepen
notes below retain prior READY=NO language as audit trail; authoritative flip
is `IMPLEMENTATION-READY-GATE.md`.

Idle Track B lanes inventoried `docs/atlas-2.0/**`. Production semantics still
require separate work-package authority after this READY stamp.

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
| Z15 | Agent OS (PROTOTYPE) | PREP | NO |
| Z16 | Digital Twin (PROTOTYPE) | PREP | NO |
| Z17 | KCI — Knowledge Compilation Interface | PREP | NO |
| Z18 | Context assembly envelope | PREP | NO |
| Z19 | Architecture sketch (PREP) | PREP | NO |
| Z20 | Schema/API drafts (non-shipping) | PREP | NO |
| Z21 | MCP/tool API drafts | PREP | NO |
| Z22 | Reality Gap analysis | PREP | NO |
| Z23 | Obsidian 2.0 non-canonical UX | PREP | NO |
| Z24 | Performance budgets | PREP | NO |
| Z25 | Test strategy | PREP | NO |
| Z26 | Migration strategy | PREP | NO |
| Z27 | DAG freeze draft | PREP | NO |

## Status notes (deepen-g / PREP)

All notes below are Track B progress only. None flip READY.

| ID | Prep status note |
|---|---|
| Z1 | CHARTER.md present as PROTOTYPE purpose envelope; not certified. |
| Z2 | VISION.md themes drafted; explicitly non-normative. |
| Z3 | PRD.md + PACKAGE-CONTRACT-STUBS FR-2.0-xxx seed; placeholders only. |
| Z4 | DAG.md carries observed prep tip; certified 1.0 snapshot pin still pending RELEASE CERTIFIED. |
| Z5 | THREAT-MODEL.md register T-2.0-001…024; mitigations = design intent. |
| Z6 | AS-2.0-FED-001 stubs + OQ-001…003 + OQ-016 open; no join schema shipped. |
| Z7 | AS-2.0-UX-001 stubs blocked on WEB APPLICATION ACCEPTED = NO; false-stamp question OQ-017 open. |
| Z8 | AS-2.0-PROV-001 stubs + OPENAI-MCP-DESIGN PROTOTYPE; no SDK wiring. |
| Z9 | AS-2.0-SYNC-001 stubs; tombstone/conflict/queue authorization unresolved (OQ-011/012/018). |
| Z10 | COMPATIBILITY.md snapshot pin model sketched; consumer not frozen. |
| Z11 | FIXTURE-PLAN.md + fixtures/README scenario/evidence-class inventory; no payload harness. |
| Z12 | OPENAI-MCP-DESIGN.md marked PROTOTYPE; production wiring forbidden. |
| Z13 | OPEN-QUESTIONS.md OQ-001…019 unanswered; research blockers intact. |
| Z14 | PROTOTYPE-MARKERS.md + `prototypes/` stub; READY firewall explicit NO. |
| Z15 | AGENT-OS.md + session prototype stub; no production wiring. |
| Z16 | DIGITAL-TWIN.md; estate twin blocked on PILOT. |
| Z17 | KCI.md interface sketch; no public API freeze. |
| Z18 | CONTEXT.md assembly envelope; no production context API. |
| Z19 | ARCHITECTURE.md layering sketch; non-normative. |

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


## Deepen-g delta (no readiness credit)

- Observed prep ancestry is now pinned to `bfdc5862b46c7e8da8fff26224fac8b7b6a2f59`
  / tree `fa404c270c1659d4c48739440a43087a4226b939`; it is not a certified snapshot.
- Contract review now separates candidate FR completeness, INV falsification,
  rejection classes, and missing evidence; every checklist row remains NO.
- Fixture inventory names deterministic oracles and promotion exits while
  retaining zero payloads and zero executable runners.
- Threat residuals cover confused-deputy capability, context replay, error
  leakage, and resource amplification; mitigations remain design intent.
- The review walkthrough is explicitly PROTOTYPE / NON-PRODUCTION and provides
  no gate evidence. OQ-001…019 remain unanswered.

`ATLAS_2_0_IMPLEMENTATION_READY = NO`.

## Deepen-h delta (no readiness credit)

- Added PROTOTYPE theme docs: AGENT-OS, DIGITAL-TWIN, KCI, CONTEXT + ARCHITECTURE sketch.
- Z15–Z19 lanes registered; freeze rows and gates 1–3/10 remain NO.
- Honest prep estimate after deepen-h: **~68%** of Track B *prep artifacts*;
  **IMPLEMENTATION READY still NO** because gates 1–3 and 10 are owner/1.0 blocked
  and §98 freeze rows remain unchecked.

| Gap blocking READY flip | Status |
|---|---|
| Gate 1 RELEASE CERTIFIED | NO |
| Gate 2 WEB ACCEPTED | NO |
| Gate 3 ESTATE PILOT / waiver | NO |
| Gate 4 §98 contract freeze | all rows NO |
| Gate 5 DAG certified 1.0 pin | partial (observed tip only) |
| Gate 6 threat register | partial / design intent |
| Gate 7 fixture harness | inventory only |
| Gate 8 OpenAI/MCP | PROTOTYPE present |
| Gate 9 compatibility consumer | partial |
| Gate 10 owner auth | NO |

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
| Z14 | [PROTOTYPE-MARKERS.md](PROTOTYPE-MARKERS.md), [prototypes/README.md](prototypes/README.md), [prototypes/REVIEW-WALKTHROUGH-PROTOTYPE.md](prototypes/REVIEW-WALKTHROUGH-PROTOTYPE.md), [IMPLEMENTATION-READY-GATE.md](IMPLEMENTATION-READY-GATE.md) |


| Z20 | [SCHEMA-API-DRAFTS.md](SCHEMA-API-DRAFTS.md) |
| Z21 | [MCP-API-DRAFTS.md](MCP-API-DRAFTS.md) |
| Z22 | [REALITY-GAP.md](REALITY-GAP.md) |
| Z23 | [OBSIDIAN-2.0.md](OBSIDIAN-2.0.md) |
| Z24 | [PERFORMANCE-BUDGETS.md](PERFORMANCE-BUDGETS.md) |
| Z25 | [TEST-STRATEGY.md](TEST-STRATEGY.md) |
| Z26 | [MIGRATION-STRATEGY.md](MIGRATION-STRATEGY.md) |
| Z27 | [DAG-FREEZE-DRAFT.md](DAG-FREEZE-DRAFT.md) |
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
| 2026-08-09 | deepen-g: refreshed prep pin; deepened review, fixture oracle, threat residual, and prototype notes; READY=NO |

# PREP — Knowledge CI engine fixture plan

Status: **PREP ONLY** — names reserved; payloads absent.
Package: `AS-2.2-KCI-ENGINE-PREP-001`.

See also: [`../fixtures/kci-engine/README.md`](../fixtures/kci-engine/README.md).

---

## Policy

- Docs-only sketches under `docs/atlas-2.2/fixtures/kci-engine/`.
- Do **not** create JSON/YAML payloads until post-`v2.1.0` unlock + contract
  freeze for `AS-2.2-KCI-001`.
- Do **not** wire these paths from production code or CI.
- Mutates vault? **No** (narrative inventory only).

---

## Fixture families (names reserved)

| Family | Path (sketch) | Purpose | Mutates vault? |
|---|---|---|---|
| Suite smoke | `fixtures/kci-engine/suite-smoke/` | Minimal suite + expect report shape | **no** |
| Authority refuse | `fixtures/kci-engine/authority-refuse/` | Promote / silent-winner negatives | **no** |
| Conflict visibility | `fixtures/kci-engine/conflict-visibility/` | Unresolved conflict unit outcomes | **no** |
| Provenance gate | `fixtures/kci-engine/provenance-gate/` | Incomplete lineage → fail/error | **no** |
| Determinism replay | `fixtures/kci-engine/determinism-replay/` | Byte-identical report on replay | **no** |
| Evidence class wall | `fixtures/kci-engine/evidence-class-wall/` | Fixture green ≠ PILOT PASS | **no** |

---

## Scenario inventory

| Scenario ID | Family | Evidence class | Positive sketch | Required negative sketch | Gate credit |
|---|---|---|---|---|---|
| FX-2.2-KCI-001 | suite-smoke | fixture rehearsal | suite loads; all units `pass` in narrative | malformed `unit_id` → load `error` | **none** |
| FX-2.2-KCI-002 | authority-refuse | fixture rehearsal | suite with `promote: false` accepted | `promote: true` refused | **none** |
| FX-2.2-KCI-003 | conflict-visibility | fixture rehearsal | unresolved conflict → unit `pass` | silent winner observed → `fail` | **none** |
| FX-2.2-KCI-004 | provenance-gate | fixture rehearsal | complete hash+lineage → `pass` | missing lineage → `error` | **none** |
| FX-2.2-KCI-005 | determinism-replay | fixture rehearsal | two evaluations → same report digest | injected timestamp field → `error` | **none** |
| FX-2.2-KCI-006 | evidence-class-wall | evidence-class sketch | report `evidence_class=fixture` | fixture receipt must not satisfy PILOT | **none** |

---

## Inventory state legend

| State | Meaning | Gate value |
|---|---|---|
| reserved | name documented | none |
| sketched | positive + negative in prose | none |
| payload-present | future review payload | none |
| harness-certified | post-READY governor evidence | not available |

**Current state for every family: reserved/sketched only.**

---

## Review checklist for future payloads (all NO today)

- [ ] **NO** — no secrets, credentials, personal data, or raw provider output
- [ ] **NO** — all paths synthetic / vault-relative
- [ ] **NO** — expected results include explicit failure classes
- [ ] **NO** — byte/digest comparison rule documented
- [ ] **NO** — fixture / waiver / acceptance / pilot classes not conflated
- [ ] **NO** — outside production package data until authorized

---

## Relation to 2.0 KCI harness fixtures

2.0 `knowledge-ci-harness` remains the **gate catalog** fixture surface.
2.2 engine fixtures add **knowledge unit evaluation** scenarios. They do not
replace or relabel 2.0 harness receipts as intelligence-certified.

`ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`.

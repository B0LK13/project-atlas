# PREP — Reality Gap fixture plan

Status: **PREP ONLY** — sketches + sample payloads under this tree.  
Package: `AS-2.2-REALITY-GAP-PREP-001`.

See also: [`fixtures/README.md`](fixtures/README.md).

---

## Policy

- Docs-owned payloads under `docs/atlas-2.2/reality-gap/fixtures/`.
- Do **not** wire these paths from production code or CI gates.
- Do **not** mutate `docs/atlas-2.0/fixtures/reality-gap/` in this package.
- Mutates vault? **No** (narrative / rehearsal inventory only).

---

## Fixture families

| Family | Path | Purpose | Mutates vault? |
|---|---|---|---|
| Inventory smoke | `fixtures/inventory.fixture.json` | Schema-shaped positive inventory | **no** |
| Unknown≠healthy | `fixtures/negative-unknown-as-healthy.fixture.json` | Reject unknown coerced to healthy | **no** |
| UI≠canonical | `fixtures/negative-ui-canonical.fixture.json` | Reject canonical_writes=true | **no** |
| No PILOT invent | `fixtures/negative-pilot-invent.fixture.json` | Reject invent_pilot_roots / pilot_roots>0 | **no** |

---

## Scenario inventory

| Scenario ID | Family | Evidence class | Positive sketch | Required negative sketch | Gate credit |
|---|---|---|---|---|---|
| FX-2.2-RG-001 | inventory smoke | fixture-only | six gap rows; pilot_roots=0 | malformed gap_id | **none** |
| FX-2.2-RG-002 | unknown≠healthy | fixture-only | status unknown retained | unknown→healthy mapping | **none** |
| FX-2.2-RG-003 | UI≠canonical | fixture-only | read_only panels | canonical_writes true | **none** |
| FX-2.2-RG-004 | no PILOT invent | fixture-only | invent_pilot_roots false | pilot_roots>0 invent | **none** |

---

## Evidence class wall

| Class | Value |
|---|---|
| Fixture rehearsal | YES (docs) |
| Production coverage | NO |
| Authentic PILOT | NO |
| Release credit | NO |
| `ATLAS_2_1_RELEASE_CERTIFIED` | **NO** |

## Relation to 2.0 fixtures

2.0 `docs/atlas-2.0/fixtures/reality-gap/` remains the **shipped** fixture
inventory surface for `AS-2.0-REALITY-GAP-001`.  
2.2 prep fixtures add **invariant rehearsal** payloads and must not replace or
relabel 2.0 receipts as intelligence-certified.

# Reality Gap — hard invariants (PREP)

Package: **AS-2.2-REALITY-GAP-PREP-001**  
Status: **normative for this PREP tree**; runtime enforcement deferred until unlock.

## 1. unknown ≠ healthy

| Signal | Allowed interpretation | Forbidden interpretation |
|---|---|---|
| status `unknown` | insufficient evidence | healthy / addressed / READY |
| missing health field | treat as unknown | default healthy |
| unresolved blocker | open / blocked-* | silently cleared |
| fixture PASS | rehearsal only | production health |

Any consumer (UI, ops receipt, future API) that coerces unknown → healthy is
**out of contract**.

## 2. UI ≠ canonical

| Surface | May do | Must not do |
|---|---|---|
| Reality Gap UI panels | Render inventory; link to docs | Write Layer B / claims |
| UI catalog record | `canonical_writes=false`, `read_only=true` | Promote authority |
| Operator actions | Open review / escalate | Stamp RELEASE from panel |

Truth boundary string (prep):  
`REALITY GAP UI ≠ CANONICAL WRITE / ≠ PILOT PASS / ≠ HEALTHY FROM UNKNOWN`

## 3. no PILOT invent

| Field | Const / rule |
|---|---|
| `pilot_roots` | `0` |
| `invent_pilot_roots` | `false` |
| `authentic_estate` | `false` on every scenario |
| `authentic_estate_pilot_passed` | `false` on inventory |
| evidence_class | `fixture-only` in this PREP |

Fixture twin ≠ authentic estate PILOT PASSED.  
Waiver / fixture rehearsal never substitutes for PILOT roots.

## 4. Certification wall

This PREP asserts:

- `ATLAS_2_1_RELEASE_CERTIFIED = NO`
- `ATLAS_2_2_INTELLIGENCE_IMPLEMENTATION_UNLOCKED = NO`

Fixture success does **not** flip either flag.

# D-176 / D149-R1 — AUTHENTIC-ESTATE residual-dependency non-widening

```
FINDING_ID = D149-001
PACKAGE    = D-176 / D149-R1
BASE       = f65e94f3f2dcf0cee96cd9932069792e320032de (post-#476 main)
MERGE_AUTHORIZATION = NOT_GRANTED
```

## Invariant

After consuming `AUTHENTIC_ESTATE_ROOT`, if residual dependencies remain:

`OWNER_GATE != NONE`

Estate availability ≠ owner authority over unrelated outstanding deps.

## Root cause

`refresh_authentic_o2_node_states` cleared `OWNER_GATE CREDENTIAL → NONE` whenever the
estate dependency was removed, without requiring `DEPENDENCIES == []`.

## Fix

Clear CREDENTIAL to NONE only when the dependency list is empty after estate consumption.
Preserve blocking CREDENTIAL when residuals (e.g. `HUMAN_APPROVAL`, other credentials) remain.
If gate was already NONE with residual deps after estate consume, restore CREDENTIAL
(absolute: residual ⇒ OWNER_GATE ≠ NONE).
No typed gate remapping invented here.

## Acceptance

- CASE A: estate-only → deps=[], OWNER_GATE=NONE, READY
- CASE B/C: residual deps → OWNER_GATE=CREDENTIAL (≠ NONE)
- CASE D/F: immutable gates / terminal statuses unchanged

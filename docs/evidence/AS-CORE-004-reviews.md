# AS-CORE-004 Independent Reviews (Candidate)

**CANDIDATE HEAD**: `1a93a27b53642ae101ea3635d37270197221bc5b`  
**CANDIDATE TREE**: `339ac0acbb02542a53c62585e105ba89ae32cf94`  
**BASE**: `7bf974623071ac946ed542fffc84f134887eeae7`

## Technical review

Inspected: semantic model, subject derivation, dimension normalization, claim
integration, migration, conflict behavior, RAW corpus reconciliation.

**Result**: NO BLOCKER

- Global `ID_PATTERN` unchanged; Claim Identity v2 algorithm diff zero.
- Subjects are structured `kind`+`key` with dedicated serialization.
- 1:M splits never auto-alias; `SEMANTIC_REFINEMENT_SPLIT` is formal.
- RAW self-host: 91 claims retained; collapse-subject conflicts = 0.

## Product-contract review

**Result**: NO BLOCKER

- 9/9 real fixture patterns green.
- True-conflict same-subject/same-dimension fixture preserved.
- Scope stayed bounded (no authority/temporal/query).
- Level 2 explicitly **NOT ACHIEVED** (remaining: authority, temporal, query).

## Adversarial review

Attacks considered: subject spoofing, duplicate definitional IDs, Unicode NFC,
1:M migration, source movement, partial extraction, true-conflict suppression,
determinism.

**Result**: NO BLOCKER

- Path-like / control / oversized keys rejected.
- Definitional duplicate WP/ADR IDs fail closed without path-order winners.
- PARTIAL sources do not promote uncertain subjects.
- Settled replay: zero unexplained canonical mutation.
- Disabling conflict comparison was not used to clear false conflicts.

# AS-CORE-004 Independent Reviews (Candidate)

**BASE**: `7bf974623071ac946ed542fffc84f134887eeae7`

## Previous review history (superseded)

**PREVIOUS IMPLEMENTATION FREEZE HEAD**: `1a93a27b53642ae101ea3635d37270197221bc5b`  
**PREVIOUS DOCUMENTED CANDIDATE HEAD**: `bb16be82d848251ca9064f9c6f2ccc6255f81599`  
**SUPERSEDED BY**: final-delta remediation under
`D-PROJECT-ATLAS-CURSOR-AS-CORE-004-FINAL-REMEDIATION-001`

Those prior NO BLOCKER notes applied to an earlier freeze and are retained only
as history. They are **not** reviews of the current remediation implementation
head.

## Final-delta review (current)

**REVIEWED_IMPLEMENTATION_HEAD**: `9ef79a4d4c168f525abe2a3dd550002d2fd10921`  
**EVIDENCE_PREPARED_FROM**: `9ef79a4d4c168f525abe2a3dd550002d2fd10921`  
**PRE-REMEDIATION HEAD**: `8e70cb1bb73981e989009f0b2bb8db3bd6cf9211`

Remediation scope reviewed:

1. Runtime semantic-subject key grammar aligned to ASCII `SUBJECT_KEY_PATTERN`
   (NFC normalize, then bounded ASCII validation; no `str.isalnum()` Unicode
   acceptance). Runtime/schema parity invariant added.
2. Duplicate semantic-subject fail-closed withholding made fully explicit
   (definitional sources/paths, all withheld claim IDs, all affected sources,
   including third-party references).
3. Fixture portability: vendored `tests/fixtures/as-core-004/` — no
   `D:/project-atlas-orphans` dependency in repository tests.

### Technical review

Inspected against exact `REVIEWED_IMPLEMENTATION_HEAD`: semantic model,
subject derivation, dimension normalization, claim integration, migration,
conflict behavior, duplicate-subject accounting, schema parity, RAW corpus
reconciliation.

**REVIEW_RESULT**: NO BLOCKER

- Global `ID_PATTERN` unchanged; Claim Identity v2 algorithm markers unchanged.
- Runtime and JSON Schema semantic-subject key grammars agree (ASCII).
- Duplicate subject withholding diagnostics account for all dependent claims.
- RAW self-host: 91 claims retained; collapse-subject conflicts = 0.

### Product-contract review

**REVIEW_RESULT**: NO BLOCKER

- 9/9 real fixture patterns green.
- True-conflict same-subject/same-dimension fixture preserved.
- Scope stayed bounded (no authority/temporal/query; no Unicode subject ID
  expansion).
- Level 2 explicitly **NOT ACHIEVED**.

### Adversarial review

Attacks considered against exact `REVIEWED_IMPLEMENTATION_HEAD`: subject
spoofing, non-ASCII/confusable keys, duplicate definitional IDs with
third-party references, 1:M migration, source movement, partial extraction,
true-conflict suppression, determinism, silent drop of dependent claims.

**REVIEW_RESULT**: NO BLOCKER

- Non-ASCII / control / path-like / oversized keys rejected after NFC.
- Definitional duplicate WP/ADR IDs fail closed without path-order winners;
  third-party references withheld and accounted.
- PARTIAL sources do not promote uncertain subjects.
- Settled replay: zero unexplained canonical mutation.
- Disabling conflict comparison was not used to clear false conflicts.

### Final-delta note

Any subsequent evidence-only commit after
`9ef79a4d4c168f525abe2a3dd550002d2fd10921` must remain docs/evidence-only and
is verified separately as `R..E` with no production delta.

# Evidence — AS-D149R2-EVIDENCE-BINDING-001

Package: `AS-D149R2-EVIDENCE-BINDING-001`
Date: 2026-08-23
Base: `4e71cce0d1c97f408347e256300a41590da4c352`

## Purpose

D-148 certification (`d148_evidence_applies`) must bind to estate identity.
A packet missing `estate_fingerprint`, or whose current fingerprint is empty
(marker removed), must not remain current.

This is a residual of D-149 (draft `#446`): the original owner-gate bypass
(`OWNER_GATE=MERGE → NONE`, `OWNER_CAPABILITY_GRANTED=True` from filesystem)
is remediated on `#446`. This package hardens the certification-side skip-if-absent
fingerprint path that remains on live `main`.

## Invariants

- Missing `AUTHENTIC_ESTATE_ROOT` on the packet → reject
- Missing `estate_fingerprint` on the packet → reject
- Empty current fingerprint → reject
- Fingerprint mismatch → reject
- Bound current estate + head + root + fingerprint → accept

## Honesty

- `OWNER_GATE_ESCALATION_ON_MAIN = STILL_PRESENT` (owned by draft `#446`)
- `AUTHENTIC_PILOT = NOT_CLAIMED`
- `MERGE_AUTHORIZATION = NOT_GRANTED`

## Validation

```
pytest tests/unit/test_d148_authentic_estate.py --no-cov
```

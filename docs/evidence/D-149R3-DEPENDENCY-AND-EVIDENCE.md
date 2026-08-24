# D-149R3 — MERGE dependency preservation + fail-closed evidence

**Package:** `AS-D149R3-DEPENDENCY-AND-EVIDENCE-001`  
**Base main:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Base tree:** `e9919f5d04bd1613df7254e3281badcdd7832b86`  
**Predecessor:** draft `#446` (`CERTIFY_WITH_RESIDUALS`)  
**Merge authorization:** `NOT_GRANTED`

## Residuals closed

Independent verification of `#446` found two MEDIUM residuals that did
not reopen `OWNER_GATE=MERGE → NONE` but still weakened integrity:

1. **R-1:** SUPERSEDED reconciler overwrote `DEPENDENCIES` on MERGE nodes
   (`PR431` → `AUTHENTIC_ESTATE_ROOT`) while preserving `OWNER_GATE`.
2. **R-2:** `d148_evidence_applies()` skipped fingerprint checks when the
   field was absent, so a drifted corpus with a fingerprint-less cert
   stayed current.

## Post-remediation

- Protected owner gates keep original dependencies and acceptance criteria.
- D-148 certification packets require recorded root + fingerprint and a
  matching current fingerprint.

## Tests

- `test_reconciler_preserves_superseded_merge_dependencies`
- `test_reconciler_does_not_rewrite_superseded_merge_to_credential` now
  also asserts `DEPENDENCIES == ["PR431"]`
- `test_d148_evidence_requires_fingerprint`
- `test_d148_evidence_rejects_empty_current_fingerprint`
- `test_d148_evidence_rejects_fingerprint_mismatch`
- `test_d148_evidence_rejects_missing_estate_root`
- `test_d148_evidence_accepts_bound_current_estate`

## Not claimed

- `AUTHENTIC_PILOT=YES`
- Merge eligibility
- Draft `#447` freshness/isolation packages (separate lane)

# D-150 — Estate corpus fingerprint

**Package:** `AS-D148-ESTATE-CORPUS-FINGERPRINT-001`  
**Base main:** `4e71cce0d1c97f408347e256300a41590da4c352`  
**Merge authorization:** `NOT_GRANTED`

## Defect

`estate_fingerprint()` hashed only `.atlas-project.yaml`. An owner could edit
authentic-estate documents without changing the marker; D-148/D-149 credentials
and O2 certificates remained current.

## Fix

Fingerprint binds marker bytes plus a deterministic SHA-256 of estate source
files (excludes `.git` / `.atlas` / VCS and common vendor dirs; 5000-file cap).
A corpus edit without a marker change invalidates the bound credential.

## Tests

- `tests/unit/test_d148_authentic_estate.py::test_estate_fingerprint_changes_when_document_changes`
- `tests/unit/test_d149_owner_gate_non_escalation.py::test_corpus_edit_rejects_stale_estate_credential`

## Not claimed

- Authentic O2 rerun
- Merge authorization

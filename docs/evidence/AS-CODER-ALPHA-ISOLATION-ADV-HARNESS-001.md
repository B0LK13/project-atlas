# AS-CODER-ALPHA-ISOLATION-ADV-HARNESS-001

**Package:** AS-CODER-ALPHA-ISOLATION-ADV-HARNESS-001  
**Base:** `f0e0c979e8ead0fdad4cc51682c560299db0a074` (post-#470 main)  
**Carrier:** `feat/d164-isolation-adv-harness` (fresh reconstruction; stale #423 not merged)

## Contract

Tests-first adversarial harness against landed inventory_drift / overview / architecture APIs.
Does **not** import or duplicate #405 `source_drift_scope`. No production rewrite. No new CLI.

## Acceptance matrix

```
CROSS_PROJECT_LEAK = 0
SECRET_ECHO = 0
PATH_ESCAPE = rejected
UNC_ROOT_ESCAPE = rejected
FORGED_PROJECT_IDENTITY = rejected
LENS_IS_AUTHORITY = NO
UNKNOWN_IS_HEALTHY = NO
STALE_AS_CURRENT = NO
```

## Local verification

Run on exact carrier tip after commit:

- `pytest tests/unit/test_as_coder_alpha_isolation_adv_001.py`
- `ruff check tests/unit/test_as_coder_alpha_isolation_adv_001.py`

## Authority

```
MERGE_AUTHORIZATION = NOT_GRANTED
INDEPENDENT_IV = REQUIRED
CERTIFICATION = NOT_GRANTED
```

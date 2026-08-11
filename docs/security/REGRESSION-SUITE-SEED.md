# Security regression suite — SEED (S08)

| Field | Value |
|---|---|
| Package | SECURITY ALPHA S08 |
| Status | **SECURITY_REGRESSION_SEED** · **AWAITING_CODEX_VALIDATION** |
| Honesty | Does **not** mark any `CODEX-SEC-### = VALIDATED_FIXED` |
| Base | `origin/main` @ `f420e4e` |

## Purpose

Add a coherent **executable** registry under `tests/security/` for Alpha
vulnerability classes listed in SECURITY-ALPHA-CLOSURE-002 §14:

provenance · trusted exec · root auth · path · secrets · request auth ·
capability · readiness · receipt

This seed does **not** re-implement remedi already open in:

| PR | Findings | Authoritative tests (on remedi branch) |
|---|---|---|
| #261 | SEC-021 | `atlas-vault-documentation/tests/test_sec021_trusted_exec.py` |
| #262 | SEC-006 | `tests/unit/test_codex_sec_006_secret_import.py` |
| #263 | SEC-004/014/017/018 | `tests/unit/test_sec_004_018_path_containment.py` |
| #264 | SEC-009 | `tests/unit/test_as_sec_009_api_auth.py` |
| #265 | SEC-015/016/019 | `atlas-vault-documentation/tests/test_sec_015_016_019_authority.py` |
| S02 (landing) | SEC-001/002 | `tests/integration/test_codex_sec_001_002_provenance.py` |

## Behavior on current main

Parametrized guards **skip** with an explicit finding/PR reason until the
authoritative remedi test file exists on tip. After remedi merges, the same
guards assert the remedi test still declares its `CODEX-SEC-*` IDs.

Run:

```bash
python -m pytest -m security_regression
```

## Non-goals

- No product feature work
- No merge of remedi PRs
- No duplication of remedi fix code
- No Codex `VALIDATED_FIXED` claims

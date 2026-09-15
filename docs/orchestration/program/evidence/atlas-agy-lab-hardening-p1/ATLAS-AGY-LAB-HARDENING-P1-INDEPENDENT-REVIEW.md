# ATLAS-AGY-LAB-HARDENING-P1 — Independent Review

**Verdict:** `PASS`  
**ready_for_integration_handoff:** `true`  
**reviewer_agent_id:** `b9085571-cb98-4b66-ae91-6cb476a2043a`  
**examined_HEAD:** `89e0e044f560536357401a0bcdc9ed2c5e25bf59`  
**branch:** `supervisor/agy-lab-hardening-p1` (uncommitted local changes only)

## Scope

Read-only review of working-tree vs HEAD:

- `experiments/agents_sdk/lab.py`
- `experiments/agents_sdk/tests/test_lab.py`

No product files were modified. Evidence-only write.

## Hashes

| Artifact | SHA-256 |
|----------|---------|
| `lab.py` | `effb9b64dbdfa5541fde38ff1113695521e9c4f0cab5aab68adf622426ca5e43` |
| `test_lab.py` | `fe16dda94393f05c8a3fa093c8117bd3cafeecb4033614126986b92a49946bf7` |
| `git diff --binary HEAD -- <two files>` | `6fe1a7d03f2a330b7fd7f18c3d7324180665d72bb6e97887eb72e1cea22eba66` |

## Checklist results

| # | Criterion | Result |
|---|-----------|--------|
| 1 | No claim that `isinstance(content, dict)` fully excludes dynamic mappings / TOCTOU | **PASS** — header honesty bounds explicitly deny that claim; Contract B uses `Mapping` + `dict()` snapshot |
| 2 | Explicit Contract B **or** A (one only), documented | **PASS** — `CONTENT_CONTRACT = "B"`; Contract B documented in module banner |
| 3 | After validation, verdict + claim_integrity from same local snapshot | **PASS** — `validate_verifier_report` returns snapshot; `Governor.run` feeds that into `gate_fields_from_verifier_snapshot` only |
| 4 | Required meaningful tests present | **PASS** — see test coverage below |
| 5 | Missing implementer role on flat dicts = compatibility, not strong identity | **PASS** — docstring + `test_implementer_flat_dict_missing_producer_role_allowed_compat_only` |
| 6 | Compat claim = source-compatible `governor.run(request)`, not 100% binary | **PASS** — lines 22–25 and `run()` docstring |
| 7 | No remaining TOCTOU / authenticity / compatibility overclaims | **PASS** — honesty bounds qualify snapshot scope; no binary/100% claims |

## Required test coverage (item 4)

| Requirement | Test |
|-------------|------|
| verifier `AgentEnvelope` `producer_role=None` / `""` | `test_verifier_envelope_producer_role_none_rejected`, `test_verifier_envelope_producer_role_empty_rejected` |
| implementer `AgentEnvelope` `producer_role=None` / `""` | `test_implementer_envelope_producer_role_none_rejected_by_verifier`, `test_implementer_envelope_producer_role_empty_rejected_by_verifier` |
| dict without `producer_role` implementer (compat) / verifier (reject) | `test_implementer_flat_dict_missing_producer_role_allowed_compat_only`, `test_verifier_mapping_missing_producer_role_rejected` |
| custom `Mapping` | `test_custom_mapping_is_accepted_via_contract_b_snapshot`, `test_custom_mapping_verifier_report_materialized` |
| dict subclass overridden `get()` | `test_dict_subclass_overridden_get_does_not_poison_snapshot_gate_fields` |
| source mutated after snapshot | `test_source_mutation_after_snapshot_does_not_affect_gate_fields` |
| `governor.run(request)` without injection | `test_governor_run_call_site_source_compatible_without_injection` |

## Commands and results

Note: worktree has no local `.venv`. Interpreter used: `[SOURCE-HOST VENV PYTHON]`.

```text
$ git rev-parse HEAD
→ exit 0 ; 89e0e044f560536357401a0bcdc9ed2c5e25bf59

$ sha256sum experiments/agents_sdk/lab.py experiments/agents_sdk/tests/test_lab.py
→ exit 0 ; hashes above

$ git diff --binary HEAD -- experiments/agents_sdk/lab.py experiments/agents_sdk/tests/test_lab.py | sha256sum
→ exit 0 ; 6fe1a7d03f2a330b7fd7f18c3d7324180665d72bb6e97887eb72e1cea22eba66

$ git diff --check HEAD -- experiments/agents_sdk/lab.py experiments/agents_sdk/tests/test_lab.py
→ exit 0 ; clean

$ .../project-atlas/.venv/bin/python -m pytest experiments/agents_sdk/tests/test_lab.py -v --tb=short
→ exit 0 ; 22 passed in 0.31s

$ .../project-atlas/.venv/bin/python -m pytest experiments/agents_sdk/tests -v --tb=short
→ exit 0 ; 28 passed in 0.12s

$ .../project-atlas/.venv/bin/python -m ruff check experiments/agents_sdk/lab.py experiments/agents_sdk/tests/test_lab.py
→ exit 0 ; All checks passed!

$ .../project-atlas/.venv/bin/python -m mypy experiments/agents_sdk/lab.py experiments/agents_sdk/tests/test_lab.py
→ exit 0 ; Success: no issues found in 2 source files
```

## Findings

None. `findings: []`

## Notes (non-blocking)

- Shallow `dict(mapping)` is adequate for current string gate fields; honesty text already states the caller's original object is not frozen.
- Runtime Task agent id unavailable → `reviewer_agent_id = b9085571-cb98-4b66-ae91-6cb476a2043a`.

## Evidence paths

1. `[SOURCE-HOST EVIDENCE DIR]/ATLAS-AGY-LAB-HARDENING-P1-INDEPENDENT-REVIEW.json`
2. `[SOURCE-HOST EVIDENCE DIR]/ATLAS-AGY-LAB-HARDENING-P1-INDEPENDENT-REVIEW.md`

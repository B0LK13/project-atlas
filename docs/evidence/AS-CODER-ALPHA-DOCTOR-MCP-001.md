# Evidence — AS-CODER-ALPHA-DOCTOR-MCP-001

PACKAGE: `AS-CODER-ALPHA-DOCTOR-MCP-001`
DATE: 2026-08-25
BASE: `f0e0c979e8ead0fdad4cc51682c560299db0a074`
BASE_TREE: `ba83d96a3542f270ae99c03b59da97b0ce567ac4`
BRANCH: `cursor/atlas-autonomous-night-cycle-5723`
D149_TOUCHED: NO
MERGE_AUTHORIZATION: NOT_GRANTED
AUTHENTIC_PILOT: NO
AUTHENTIC_ESTATE_ROOT: UNSET

## Commands

```
.venv/bin/python -m pytest \
  tests/unit/test_as_coder_alpha_doctor_mcp_001.py \
  tests/unit/test_as_coder_alpha_doctor_web_001.py \
  tests/unit/test_as_coder_alpha_obsidian_mcp_001.py \
  tests/unit/test_as_coder_alpha_obsidian_web_001.py \
  tests/unit/test_as_2_1_mcp_adv_001.py \
  tests/unit/test_as_2_1_mcp_brief_001.py \
  tests/unit/test_as_coder_alpha_demo_readiness_001.py \
  tests/unit/test_d148_authentic_estate.py \
  tests/unit/test_d149_terminal_evidence_integrity.py \
  tests/unit/test_prod_doctor_001.py \
  tests/unit/test_as_coder_alpha_obsidian_001.py \
  -q --no-cov
```

RESULT: 81 passed (67 focused + 14 doctor/obsidian regression).

```
.venv/bin/python -m ruff check src/project_atlas/web_api/doctor.py \
  src/project_atlas/web_api/obsidian.py src/project_atlas/api_server.py
.venv/bin/python -m mypy src
```

RESULT: pass.

## Independent verification

IV_RESULT=PASS (explore verifier; implementer ≠ verifier)
D149_TOUCHED=NO
P0_REMAINING=
P1_REMAINING=
VALID P1 (symlinked Obsidian root) remediated before this receipt:
`test_symlinked_obsidian_root_is_ignored`.

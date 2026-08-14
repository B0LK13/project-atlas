# Exact-frozen-HEAD validation commands (Cloud D-049 premerge)

Worktree: `/tmp/d049-frozen`
HEAD: `0509287c8915f3fe06644d5a00bcc219bd290add`
TREE: `728f3af450961db00d9a310293907cd3125272f6`
`PYTHONPATH=/tmp/d049-frozen/src`
Interpreter: `/workspace/.venv/bin/python` (CPython 3.12.3)

## Commands actually run

```text
python -m pytest tests/unit/test_as_coder_alpha_049_estate_discovery.py \
  tests/unit/test_as_d049_063_truth_hardening.py \
  tests/unit/test_as_d049_064_high_remediation.py
# 30 passed

python -m pytest tests/unit/test_source_identity.py \
  tests/unit/test_as_coder_alpha_connect_001.py \
  tests/unit/test_as_coder_alpha_057_copied_uuid.py \
  tests/unit/test_claim_identity.py
# 46 passed

python -m pytest tests/unit -k 'coder_alpha or d049 or connect or source_identity'
# passed (1 skipped)

python -m pytest atlas-vault-documentation/tests
# 171 passed

python -m ruff check .
# All checks passed

python -m mypy src
# Success: no issues found in 185 source files

cd apps/web && npx tsc -b
# exit 0

cd apps/web && npm run build
# tsc -b && vite build; exit 0
```

Independent attack probes (synthetic planted token only; not production):
`/tmp/d049-independent-attack.py` against the same frozen `PYTHONPATH`.
Required remote forms: no echo. Symlink matrix: no crash / no escape.
Quoted git-config URL residual recorded in
`docs/evidence/D-049-PREMERGE-READINESS.md`.

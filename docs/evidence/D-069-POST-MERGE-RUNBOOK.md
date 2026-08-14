# D-049 post-merge seal (prepare only — do not execute)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-INTEGRATION-069`

Execute only after CASE A and explicit merge authorization.

## Preconditions

1. Local D-068 tested exact `ccacaa5` / `d26768`
2. `NEW_HIGH = 0` and `HIGH_STILL_OPEN = 0`
3. Integration tip production trees equal `ccacaa5` (`src/`, `apps/`, `tests/`, `pyproject.toml`)
4. #346 (or authorized successor) descends from `ccacaa5`
5. `D_042_EXECUTION_GATE = CLOSED`

## Capture immediately after merge

```bash
git fetch origin main
echo MERGE_COMMIT=$(git rev-parse origin/main)
echo MERGE_TREE=$(git rev-parse origin/main^{tree})
echo MERGE_PARENTS=$(git rev-parse origin/main^@)
git log -1 --format='%H %T %P %s' origin/main
```

## Production equality to D-067 freeze

```bash
git diff --name-only ccacaa5bcb094f35017c7195264fef55e382cb49 origin/main -- src apps tests pyproject.toml
# must be empty
test "$(git rev-parse origin/main:src)" = "$(git rev-parse ccacaa5bcb094f35017c7195264fef55e382cb49:src)"
test "$(git rev-parse origin/main:apps)" = "$(git rev-parse ccacaa5bcb094f35017c7195264fef55e382cb49:apps)"
test "$(git rev-parse origin/main:tests)" = "$(git rev-parse ccacaa5bcb094f35017c7195264fef55e382cb49:tests)"
```

## Bounded smoke (do not start D-042)

```bash
python -m pytest \
  tests/unit/test_as_coder_alpha_049_estate_discovery.py \
  tests/unit/test_as_d049_063_truth_hardening.py \
  tests/unit/test_as_d049_064_high_remediation.py \
  tests/unit/test_as_d049_067_high_remediation.py \
  tests/unit/test_source_identity.py \
  tests/unit/test_as_coder_alpha_connect_001.py \
  tests/unit/test_as_coder_alpha_057_copied_uuid.py
python -m pytest atlas-vault-documentation/tests
python -m pytest tests/unit -k 'coder_alpha or connect or source_identity'
cd apps/web && npx tsc -b && npm run build
```

Record `HIGH_OPEN=0`. Freeze `origin/main`. Authentic-estate remains a separate
owner-authorized run. Do not invent a root.

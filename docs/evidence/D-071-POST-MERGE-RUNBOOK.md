# D-049 post-merge exact-main seal (prepare only — do not execute)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-FINAL-RECONCILIATION-071`

Execute only after Local D-068 PASS, Cloud
`READY_FOR_FINAL_MERGE_AUTHORIZATION`, and **owner authorization** of
PR #348. Do not execute because this file exists.

## Preconditions

1. Local tested exact `ccacaa5bcb094f35017c7195264fef55e382cb49` /
   `d26768fe753c888cd45001987da2afe977c79d45`
2. `NEW_HIGH = 0` and `HIGH_STILL_OPEN = 0`
3. `#348` production trees equal `ccacaa5`
4. Owner authorized merge of #348
5. `D_042_EXECUTION_GATE = CLOSED`

## Sequence

### 1. Record previous main

```bash
git fetch origin main
echo PREVIOUS_MAIN=$(git rev-parse origin/main)
echo PREVIOUS_TREE=$(git rev-parse origin/main^{tree})
# expected PREVIOUS_MAIN=072f1395ee310a876e93d633264f3ece43cecc3c
# unless main moved; if it moved, stop and re-evaluate
```

### 2. Merge authorized PR

Use GitHub merge of https://github.com/B0LK13/project-atlas/pull/348
as a **merge commit** (not squash). Do not force-push.

### 3–5. Record merge identity

```bash
git fetch origin main
echo MERGE_COMMIT=$(git rev-parse origin/main)
echo MERGE_TREE=$(git rev-parse origin/main^{tree})
echo MERGE_PARENTS=$(git rev-parse origin/main^@)
git log -1 --format='%H %T %P %s' origin/main
```

Expected: Parent 1 is previous main; Parent 2 is the authorized #348
tip; `ccacaa5` is an ancestor of `origin/main`.

### 6–7. Verify intended production semantics

```bash
FROZEN=ccacaa5bcb094f35017c7195264fef55e382cb49
git merge-base --is-ancestor "$FROZEN" origin/main
git diff --name-only "$FROZEN" origin/main -- src apps tests pyproject.toml
# must be empty
test "$(git rev-parse origin/main:src)" = "$(git rev-parse ${FROZEN}:src)"
test "$(git rev-parse origin/main:apps)" = "$(git rev-parse ${FROZEN}:apps)"
test "$(git rev-parse origin/main:tests)" = "$(git rev-parse ${FROZEN}:tests)"
```

Any production path difference vs `ccacaa5` is a seal failure.

### 8. D-049 focused exact-main smoke

```bash
python -m pytest \
  tests/unit/test_as_coder_alpha_049_estate_discovery.py \
  tests/unit/test_as_d049_063_truth_hardening.py \
  tests/unit/test_as_d049_064_high_remediation.py \
  tests/unit/test_as_d049_067_high_remediation.py
```

### 9. Bounded identity / connect smoke

```bash
python -m pytest \
  tests/unit/test_source_identity.py \
  tests/unit/test_as_coder_alpha_connect_001.py \
  tests/unit/test_as_coder_alpha_057_copied_uuid.py
python -m pytest tests/unit -k 'coder_alpha or connect or source_identity'
```

### 10. Control Plane smoke

```bash
python -m pytest atlas-vault-documentation/tests
```

### 11. Web build

```bash
cd apps/web && npx tsc -b && npm run build
```

### 12. HIGH_OPEN

Record `HIGH_OPEN=0` from the post-merge smoke plus ingested Local
result. If any new HIGH appears, freeze is not sealed.

## Required future state

```
MERGED → POST-MERGE VERIFIED
```

Authentic-estate acceptance remains a separate owner-authorized run.
Do not invent a root. Do not start D-042.

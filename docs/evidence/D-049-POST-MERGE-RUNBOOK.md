# D-049 post-merge seal runbook (PREPARE ONLY)

DIRECTIVE: `D-PROJECT-ATLAS-CLOUD-D049-PREMERGE-066`

Do **not** execute this runbook until Local D-065 returns and merge is
explicitly authorized. This file is a deterministic checklist.

## Preconditions (all required)

1. Local tested exact `0509287c8915f3fe06644d5a00bcc219bd290add` /
   `728f3af450961db00d9a310293907cd3125272f6`.
2. `PRODUCTION_SEMANTIC_CHANGES_AFTER_FREEZE` is still `0`
   (`src/`, `apps/`, `tests/`, `pyproject.toml` unchanged vs frozen HEAD).
3. `HIGH_OPEN=0` and `NEW_HIGH=0` after Local evidence review.
4. `D049_CLOUD_RECONCILIATION=MERGE_ELIGIBLE` (Lane I Case A).
5. Owner / integration authorization granted for #346.
6. `D_042_EXECUTION_GATE` remains CLOSED.

If Local tested a different HEAD/TREE → Case D: `VALIDATION_STALE`. Stop.

## Step 1 — re-verify freeze (read-only)

```bash
git fetch origin pull/346/head
FROZEN=0509287c8915f3fe06644d5a00bcc219bd290add
TREE=728f3af450961db00d9a310293907cd3125272f6
test "$(git rev-parse ${FROZEN}^{tree})" = "$TREE"
git diff --name-only ${FROZEN} origin/cursor/d049-knowledge-estate-discovery-d036 -- src apps tests pyproject.toml
# must print nothing
```

## Step 2 — merge #346 (only after authorization)

Use the GitHub merge of https://github.com/B0LK13/project-atlas/pull/346
onto `main`. Do not force-push. Do not squash away the frozen production
commit identity unless the owner explicitly authorizes a squash and
re-records the post-merge tree.

Capture immediately after merge:

```bash
git fetch origin main
echo MERGE_COMMIT=$(git rev-parse origin/main)
echo MERGE_TREE=$(git rev-parse origin/main^{tree})
echo MERGE_PARENTS=$(git rev-parse origin/main^@)
git log -1 --format='%H %T %P %s' origin/main
```

## Step 3 — verify D-049 production is on main

```bash
git cat-file -e 0509287c8915f3fe06644d5a00bcc219bd290add
git merge-base --is-ancestor 0509287c8915f3fe06644d5a00bcc219bd290add origin/main
git diff --name-only 0509287c8915f3fe06644d5a00bcc219bd290add origin/main -- src apps tests pyproject.toml
# production paths must be empty (evidence-only diffs allowed elsewhere)
test -f src/project_atlas/estate_discovery.py
```

## Step 4 — bounded exact-main D-049 regression

```bash
git checkout origin/main
python -m pytest \
  tests/unit/test_as_coder_alpha_049_estate_discovery.py \
  tests/unit/test_as_d049_063_truth_hardening.py \
  tests/unit/test_as_d049_064_high_remediation.py \
  tests/unit/test_source_identity.py \
  tests/unit/test_as_coder_alpha_connect_001.py \
  tests/unit/test_as_coder_alpha_057_copied_uuid.py
python -m ruff check .
python -m mypy src
```

## Step 5 — Coder Alpha regression remains green

```bash
python -m pytest tests/unit -k 'coder_alpha or connect or source_identity'
```

## Step 6 — freeze main

Record `origin/main` commit + tree as the post-merge D-049 pin.
Do not start D-042. Do not open new discovery providers.

## Step 7 — prepare Local / post-merge acceptance if needed

If Windows IV already passed on exact `0509287` / `728f3af` and
production trees on main still match that pin, Local IV does not need
to be re-run for merge confirmation.

Authentic-estate dogfood remains a separate owner-authorized run
(`docs/evidence/D-049-AUTHENTIC-ESTATE-ACCEPTANCE-PLAN.md`).
`AUTHENTIC_USER_ESTATE_ACCEPTANCE` stays `NOT_YET_PROVEN` until that run.

## Explicitly out of scope

- D-042 Conversational Capture
- Project Memory / Momentum / Portfolio Intelligence
- OPT / AutoLab / Prime / 2.3 expansion
- Cloud sync / major UI redesign

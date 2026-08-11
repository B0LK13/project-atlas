# Eval fixtures (AS-2.2-EVAL-001)

- `public/` — allowed for training + autolab + scoring roles.
- `holdouts/hidden/` — holdout metadata only (no plaintext `expected` in git);
  scoring requires `ATLAS_EVAL_SCORING_CAPABILITY=1` and a private expected
  map via `ATLAS_EVAL_HOLDOUT_EXPECTED_PATH`.
- `configs/*.paths.json` — role path manifests exercised by
  `project_atlas.eval_substrate`.

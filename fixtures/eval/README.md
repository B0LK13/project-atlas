# Eval fixtures (AS-2.2-EVAL-001)

- `public/` — allowed for training + autolab + scoring roles.
- `regression/` — retired (compromised) holdouts, now PUBLIC regression cases
  (D-ULTRA-RESUME-010 §8). Readable by all roles; never treated as hidden.
- `holdouts/hidden/` — live hidden holdout metadata only (`EV-HOLD-1xx`, no
  plaintext `expected` in git); scoring requires `ATLAS_EVAL_SCORING_CAPABILITY=1`
  and a private expected map via `ATLAS_EVAL_HOLDOUT_EXPECTED_PATH`. The true
  trust boundary is the out-of-process broker (`project_atlas.scoring_broker`).
- `configs/*.paths.json` — role path manifests exercised by
  `project_atlas.eval_substrate`.

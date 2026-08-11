# Eval fixtures (AS-2.2-EVAL-001)

- `public/` — allowed for training + autolab + scoring roles.
- `holdouts/hidden/` — scoring role only; training/autolab configs must not list
  or resolve these paths.
- `configs/*.paths.json` — role path manifests exercised by
  `project_atlas.eval_substrate`.

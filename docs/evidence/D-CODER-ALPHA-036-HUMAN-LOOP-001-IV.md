# IV — AS-CODER-ALPHA-HUMAN-LOOP-001

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-OVERNIGHT-036  
**Package:** AS-CODER-ALPHA-HUMAN-LOOP-001  
**Result:** PASS after IV remediation (unknown lens uses live pending queue)

## Acceptance checked

- `atlas review decide --decision accept|reject --reason ...` is user-visible.
- Unknown/stale review ids, unsafe project ids, missing reason fail closed.
- Durable dispositions under `state/human-decisions/`; receipts under
  `generated/ops/human-decisions/`.
- Pending queue entry status updates immediately; unknown lens counts only
  `status=pending`.
- Compile honors accept (VERIFIED) and reject (REJECTED lifecycle) so reconnect
  does not resurrect decided pending-claim reviews.
- Conflict accept requires `--winner-claim-id` (no silent winners).
- No OPT/pilot claims.

## Commands

```bash
.venv/bin/python -m ruff check src/project_atlas/human_loop.py \
  src/project_atlas/knowledge_compiler.py src/project_atlas/project_unknown.py \
  src/project_atlas/cli.py tests/unit/test_as_coder_alpha_human_loop_001.py
.venv/bin/python -m mypy src/project_atlas/human_loop.py \
  src/project_atlas/knowledge_compiler.py src/project_atlas/project_unknown.py
.venv/bin/python -m pytest tests/unit/test_as_coder_alpha_human_loop_001.py \
  tests/integration/test_core_semantic_lifecycle.py -q --no-cov
```

## Explicit non-claims

- ATLAS_OPT_WAKE_GATE: CLOSED
- authentic_pilot: false
- CODEX_VALIDATED: NO

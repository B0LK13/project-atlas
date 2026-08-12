# IV — AS-CODER-ALPHA-CAPTURE-001

**Directive:** D-PROJECT-ATLAS-CODER-ALPHA-OVERNIGHT-036  
**Package:** AS-CODER-ALPHA-CAPTURE-001  
**Result:** PASS (local gates before PR)

## Acceptance checked

- Explicit `atlas capture record` writes durable ops receipt under
  `generated/ops/session-captures/` with deterministic `capture-*` id.
- `atlas capture list` returns project-scoped captures.
- Agent context markdown includes `## Session memory (captures)`.
- `atlas handoff create` semi-auto captures by default (`--no-capture` opt-out).
- No wall-clock `generated_at`; UNKNOWN honesty stamps present.
- Captures are ops receipts, not Layer B authority.

## Commands

```bash
.venv/bin/python -m ruff check src/project_atlas/session_capture.py \
  src/project_atlas/agent_handoff.py src/project_atlas/cli.py \
  tests/unit/test_as_coder_alpha_capture_001.py
.venv/bin/python -m mypy src/project_atlas/session_capture.py \
  src/project_atlas/agent_handoff.py
.venv/bin/python -m pytest tests/unit/test_as_coder_alpha_capture_001.py \
  tests/unit/test_as_coder_alpha_context_handoff_001.py -q
```

## Explicit non-claims

- ATLAS_OPT_WAKE_GATE: CLOSED
- authentic_pilot: false
- CODEX_VALIDATED: NO
- No invented estate facts

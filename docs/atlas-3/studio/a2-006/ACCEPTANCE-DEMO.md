# A2-006 acceptance demonstration (local / verifier prep)

```text
PURPOSE                 = reproducible inspect-only demo
AUTO_RETRY              = false
MONITOR/SESSION/RESUME  != claim-execute
CI_PASS                 != FORMAL_IV != MERGE
MULTI_FILE_FS_SNAPSHOT  = NOT claimed (binding checks only)
POWER_LOSS_DURABILITY   = NOT claimed by process tests
```

## Prerequisites

Worktree with `feat/as-studio-a2-006-mission-session` checked out and `PYTHONPATH=scripts`.

## Demo 1 — confirmed success inspect

```bash
# Prepare fixtures (operator-supplied intent + decision JSON objects).
PYTHONPATH=scripts python - <<'PY'
import json
from pathlib import Path
from atlas_studio.action_intent import build_ownership_claim_intent
FIXED='2026-09-09T19:30:00Z'
intent=build_ownership_claim_intent(
    agent_id='agent-alpha', lane='pr/788',
    source_mc_fingerprint='a'*64, clock=lambda: FIXED)
decision={
  "schema":"ATLAS_STUDIO_ACTION_DECISION_V1",
  "decision":"EXECUTED","action_type":"OWNERSHIP_CLAIM",
  "intent_id":intent["intent_id"],"mutated":True,"reasons":[],
  "evidence":{"mutation_state":"CONFIRMED","repo":"B0LK13/project-atlas","lane":"pr/788"},
  "honesty":{
    "studio_ui_ne_authority":True,"requested_ne_claimed":True,
    "preview_ne_execution":True,"control_plane_revalidates_at_execution":True,
    "studio_never_self_authorizes":True},
  "evaluated_at_utc":FIXED}
Path('/tmp/a2-006-intent.json').write_text(json.dumps(intent,indent=2))
Path('/tmp/a2-006-decision.json').write_text(json.dumps(decision,indent=2))
print(intent['intent_id'])
PY

PYTHONPATH=scripts python -m atlas_studio mission-session \
  --intent-file /tmp/a2-006-intent.json \
  --decision-file /tmp/a2-006-decision.json \
  --json
# expect: session_state=CONFIRMED_SUCCESS, exit 0, auto_retry=false
# expect: lifecycle.snapshot_consistency.status=COHERENT when both files load
```

## Demo 2 — corrupt input

```bash
printf '{"schema":' >/tmp/a2-006-corrupt.json
PYTHONPATH=scripts python -m atlas_studio mission-session \
  --intent-file /tmp/a2-006-corrupt.json --json
# expect: session_state=CORRUPT_INPUT, exit 1, recovery.auto_retry=false
```

## Demo 3 — persistence-failed signal (no replay)

```bash
PYTHONPATH=scripts python -m atlas_studio mission-session \
  --intent-file /tmp/a2-006-intent.json \
  --decision-file /tmp/a2-006-decision.json \
  --persistence-failed-after-mutation --json
# expect: exit 3; resume.do_not forbids claim-execute replay
```

## Demo 4 — snapshot inconsistent (decision before intent request)

```bash
# Build fixtures where evaluated_at_utc < requested_at_utc (mixed-generation risk)
PYTHONPATH=scripts python -m atlas_studio mission-session \
  --intent-file /tmp/a2-006-intent-late.json \
  --decision-file /tmp/a2-006-decision-early.json --json
# expect: session_state=SNAPSHOT_INCONSISTENT, exit 1
```

## Verifier notes

- Pin the exact tip SHA under Formal IV; tip drift requires a new cycle.
- `#788` Formal IV PASS on `4904125f` does **not** transfer to #791.
- `#786` task-context remains UNAVAILABLE until present on this stack.
- Process-based cross-process tests ≠ power-loss durability.
- Byte hashes ≠ multi-file filesystem transaction.
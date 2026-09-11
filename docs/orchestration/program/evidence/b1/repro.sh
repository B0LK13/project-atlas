#!/usr/bin/env bash
# B1 reproducer: SIGKILL only the supervisor; the worker survives; reconcile lies.
# Test-owned resources only. No model calls, no registry, no operational state.
set -uo pipefail
# find_worker.py ships next to this script; resolve it from here rather than
# from one machine's cache path, or the reproducer only runs on that machine.
SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
K="$1"; S="$2"; PY="$K/.venv/bin/python"
WS="$S/ws"; ST="$S/state"
rm -rf "$WS" "$ST"; mkdir -p "$WS/src" "$ST"
git -C "$WS" init -q
printf 'seed\n' > "$WS/src/seed.txt"
git -C "$WS" -c user.email=t@t -c user.name=t add -A
git -C "$WS" -c user.email=t@t -c user.name=t commit -qm seed
HEAD=$(git -C "$WS" rev-parse HEAD)
FIX="$K/tests/unit/_program_fixture_worker.py"

cat > "$S/program.json" <<JSON
{ "schema_version": 1,
  "program": {
    "program_id": "B1-REPRO", "objective": "reproduce B1",
    "approved_by": "test", "approval_reference": "docs/orchestration/program/README.md",
    "workspace_root": "$WS", "base_pin": "$HEAD",
    "limits": {"max_cycles": 4, "idle_sleep_seconds": 0.0, "max_task_seconds": 600,
               "max_task_launches": 2},
    "tasks": [{
      "task_id": "hangs", "title": "hangs on purpose", "instruction": "hang",
      "profile_ref": "implementer", "mutation_paths": ["src"],
      "surface_id": "hangs", "surface_semantic": "HANGS",
      "capabilities_required": ["IMPLEMENT"],
      "acceptance": [{"check_id": "out", "kind": "FILE_EXISTS",
                      "description": "never written", "path": "src/never.txt"}]
    }]
  },
  "profiles": { "implementer": {
    "profile_id": "implementer", "agent_id": "b1-agent", "adapter": "local-command",
    "credential": "NOT_APPLICABLE", "capabilities": ["IMPLEMENT"],
    "allowed_mutation_prefixes": ["src"],
    "limits": {"max_seconds": 3600, "max_attempts": 2},
    "env_allowlist": ["ATLAS_FIXTURE_MODE","ATLAS_FIXTURE_TARGET","ATLAS_PROGRAM_TASK","ATLAS_PROGRAM_ATTEMPT"],
    "adapter_options": {"argv": ["$PY", "$FIX"]} } } }
JSON

export ATLAS_FIXTURE_MODE=hang
"$PY" -m project_atlas.orchestration.program.cli program start \
  --program "$S/program.json" --state-root "$ST" > "$S/start.log" 2>&1 &
SUP=$!
echo "supervisor pid $SUP"

# Wait for the worker to actually exist, then note its pid.
WORKER=""
for _ in $(seq 1 100); do
  WORKER=$("$PY" "$SELF_DIR/find_worker.py" "$FIX")
  [ -n "$WORKER" ] && break
  sleep 0.2
done
[ -z "$WORKER" ] && { echo "FAIL: worker never appeared"; kill -9 $SUP 2>/dev/null; exit 1; }
echo "worker pid $WORKER"
sleep 0.5

kill -9 "$SUP" 2>/dev/null || true
wait "$SUP" 2>/dev/null || true
echo "supervisor SIGKILLed"

if kill -0 "$WORKER" 2>/dev/null; then
  echo "ORPHAN WORKER STILL ALIVE: pid $WORKER"
else
  echo "FAIL: worker died with the supervisor; reproducer invalid"; exit 1
fi

echo "--- durable attempt record ---"
"$PY" - "$ST" <<'PYEOF'
import json, sys, pathlib
p = pathlib.Path(sys.argv[1]) / ".atlas" / "orchestration" / "program" / "state.json"
if not p.is_file():
    cands = list(pathlib.Path(sys.argv[1]).rglob("state.json"))
    p = cands[0] if cands else p
d = json.loads(p.read_text())
for a in d.get("attempts", {}).values():
    print(f"  phase={a['phase']} process_pid={a['process_pid']!r} "
          f"start_identity={a['process_start_identity']!r}")
PYEOF

echo "--- reconcile ---"
"$PY" -m project_atlas.orchestration.program.cli program reconcile \
  --program "$S/program.json" --state-root "$ST" 2>&1 | tail -40

kill -9 "$WORKER" 2>/dev/null || true
echo "orphan cleaned up"

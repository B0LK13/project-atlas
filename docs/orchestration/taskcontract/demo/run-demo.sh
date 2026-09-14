#!/usr/bin/env bash
# AS-TASK-CONTRACT-001 demonstration: one real backlog item, end to end.
#
# Read-only against docs/backlog.md. Starts no worker, makes no model call, and
# executes no acceptance command. Writes only into this demo directory and the
# scratch state/registry roots it creates.
set -euo pipefail

REPO="$(cd "$(dirname "$0")/../../../.." && pwd)"
D="$REPO/docs/orchestration/taskcontract/demo"
PY="${ATLAS_PY:-$REPO/.venv/bin/python}"
SCRATCH="${ATLAS_DEMO_SCRATCH:-$HOME/.cache/atlas-taskcontract-demo}"
EV="$D/evidence"
mkdir -p "$SCRATCH/state" "$SCRATCH/registry" "$EV"

atlas() { "$PY" -m project_atlas.cli "$@" 2>/dev/null; }

echo "== 1. what the declared sources offer =="
atlas task sources --project "$REPO" > "$EV/01-sources.json"

echo "== 2. draft with NO supplied input: the gaps, named =="
atlas task draft --project "$REPO" --item INT-013 > "$EV/02-draft-incomplete.json" || true

echo "== 3. draft with the operator's explicit decisions =="
atlas task draft --project "$REPO" --item INT-013 \
  --supplied "$D/supplied.json" \
  --contract-id INT-013-BOUNDED-PILOT \
  --source-revision "$(git -C "$REPO" rev-parse HEAD)" \
  --out "$D/contract.v1.json" > "$EV/03-draft-complete.json"

echo "== 4. validate: structure, content, preconditions, authorization =="
atlas task validate --contract "$D/contract.v1.json" --binding "$D/binding.json" \
  --project "$REPO" --json-out "$D/validation.v1.json" > "$EV/04-validate-operator-view.txt" \
  && echo "   exit 0 (no ERROR)"

echo "== 5. render the instruction and the program configuration =="
atlas task render --contract "$D/contract.v1.json" --binding "$D/binding.json" \
  --profile "$D/profile.json" --approved-by wesley \
  --approval-reference "docs/origination-acceptance-contracts.yaml#INT-013" \
  --out-program "$D/program.v1.json" --out-instruction "$D/instruction.v1.md" \
  > "$EV/05-render.json"

echo "== 6. the OFFICIAL program validator checks what we generated =="
atlas program validate --program "$D/program.v1.json" --state-root "$SCRATCH/state" \
  > "$EV/06-program-validate.json"

echo "== 7. the preflight tool, when it is available here =="
PF="${ATLAS_PREFLIGHT:-}"
if [ -n "$PF" ] && [ -f "$PF" ]; then
  "$PY" "$PF" --program "$D/program.v1.json" --state-root "$SCRATCH/state" \
    --registry "$SCRATCH/registry" > "$EV/07-preflight.txt" 2>&1 || true
else
  echo "   AS-PREFLIGHT-001 not on this checkout; set ATLAS_PREFLIGHT to run it" \
    > "$EV/07-preflight.txt"
fi

echo "== 8. the review package =="
atlas task review --contract "$D/contract.v1.json" --binding "$D/binding.json" \
  --project "$REPO" --program-file "$D/program.v1.json" \
  --out "$D/review-package.v1.json" > /dev/null
cp "$D/review-package.v1.json" "$EV/08-review-package.json"

echo "== 9. a contract with concrete blockers =="
atlas task validate --contract "$D/contract.v2-blocked.json" \
  --binding "$D/binding.broken.json" --project "$REPO" \
  --json-out "$D/validation.v2-blocked.json" > "$EV/09-blocked-operator-view.txt" \
  && { echo "   UNEXPECTED: blocked example exited 0"; exit 1; } \
  || echo "   exit 3 (ERRORs found), as intended"

echo "== 10. what changed, and whether an earlier approval survives =="
atlas task diff --before "$D/contract.v1.json" --after "$D/contract.v2-blocked.json" \
  --binding-before "$D/binding.json" --binding-after "$D/binding.broken.json" \
  > "$EV/10-diff.json"
atlas task verify --contract "$D/contract.v2-blocked.json" \
  --report "$D/validation.v1.json" --binding "$D/binding.json" \
  > "$EV/11-verify-stale.json" || true

echo
echo "Evidence in $EV"
echo "Nothing was launched. acceptance_outcome is NOT_EVALUATED in every report."

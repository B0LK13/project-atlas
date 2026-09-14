#!/usr/bin/env bash
# ATLAS-EXECUTION-SEAM-CLOSURE-003 — reproducible entrypoint (fixture-only).
#
# Usage:
#   bash scripts/atlas-execution-seam-closure-003.sh <checkout> <scratch-dir> [python]
#
# Never launches a paid model, never mutates operational registries, never merges.
set -euo pipefail
CHECKOUT="${1:?usage: $0 <checkout> <scratch-dir> [python]}"
SCRATCH="${2:?}"
PY="${3:-python3}"
export PYTHONPATH="$CHECKOUT/src:${PYTHONPATH:-}"
mkdir -p "$SCRATCH"
cd "$CHECKOUT"
"$PY" -m pytest \
  tests/unit/test_execution_seam_closure_003.py \
  tests/unit/test_b1_inflight_process_visibility.py \
  tests/unit/test_execution_seam_controlled_chain.py \
  tests/unit/test_taskcontract_preparation.py \
  -q --tb=short
echo "SEAM_CLOSURE_003_ENTRYPOINT=PASS (fixture regressions)"

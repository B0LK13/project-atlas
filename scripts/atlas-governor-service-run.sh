#!/usr/bin/env bash
# Least-privilege durable Atlas governor host (Windows/WSL foreground process).
# Does not merge. Does not grant authority. Primary backend: Cursor SDK.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
export PYTHONPATH="${ROOT}/src${PYTHONPATH:+:$PYTHONPATH}"
exec python -m project_atlas.cli orchestrator governor-service-run --root "$ROOT" "$@"

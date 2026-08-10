#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Project Atlas.
# - Core: Python 3.12 package `project-atlas` installed editable into .venv with dev deps.
# - Web:  apps/web (Vite + React) dependencies installed from the committed lockfile.
set -euo pipefail

cd "$(dirname "$0")/.."

# System dependency: Ubuntu ships python3.12 without the venv/ensurepip module.
if ! python3 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3.12-venv
fi

# Python virtualenv (project convention: .venv, per AGENTS.md / CLAUDE.md).
if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

# Web app dependencies (deterministic install from package-lock.json).
npm --prefix apps/web ci

echo "Project Atlas environment ready: $(.venv/bin/atlas version 2>/dev/null | tail -1)"

#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Project Atlas.
# - Core: Python 3.12 package `project-atlas` installed editable into .venv with dev deps.
# - Web:  apps/web (Vite + React) dependencies installed from the committed lockfile.
set -euo pipefail

cd "$(dirname "$0")/.."

# Prefer explicit python3.12 (pyproject requires >=3.12). Unversioned `python3`
# may be 3.11 on some images even when ensurepip is present.
if ! command -v python3.12 >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3.12 python3.12-venv
fi

# System dependency: Ubuntu often ships python3.12 without the venv/ensurepip module.
if ! python3.12 -c "import ensurepip" >/dev/null 2>&1; then
  sudo apt-get update -qq
  sudo apt-get install -y --no-install-recommends python3.12-venv
fi

# Python virtualenv (project convention: .venv, per AGENTS.md / CLAUDE.md).
if [ ! -x .venv/bin/python ]; then
  python3.12 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

# Guard: refuse to continue if the venv interpreter is older than 3.12.
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 12), sys.version'

# Web app dependencies. The repo intentionally gitignores apps/web/package-lock.json
# (see apps/web/.gitignore), so `npm install` (per apps/web/README.md) is used rather
# than `npm ci`, which requires a committed lockfile.
npm --prefix apps/web install

# Browser for the repository-native Playwright acceptance suite (npm run test:e2e).
# Idempotent: skips the download when the browser is already cached.
npm --prefix apps/web exec -- playwright install chromium

echo "Project Atlas environment ready: $(.venv/bin/atlas version 2>/dev/null | tail -1)"

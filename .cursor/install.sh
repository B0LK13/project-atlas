#!/usr/bin/env bash
# Idempotent Cloud Agent bootstrap for Project Atlas (SEC-028).
# - LOCAL_SOURCE: Python 3.12 editable `project-atlas` into .venv with dev deps.
# - THIRD_PARTY: apps/web deps from committed package-lock.json via `npm ci`.
# Prefer locked/deterministic install. Run scripts/verify_dep_integrity.py after.
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
# LOCAL_SOURCE: editable install from this checkout (not a third-party wheel pin).
if [ ! -x .venv/bin/python ]; then
  python3.12 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e ".[dev]"

# Guard: refuse to continue if the venv interpreter is older than 3.12.
.venv/bin/python -c 'import sys; assert sys.version_info >= (3, 12), sys.version'

# Node/npm required for apps/web (idempotent; NodeSource 22.x on Ubuntu).
if ! command -v npm >/dev/null 2>&1; then
  curl -fsSL https://deb.nodesource.com/setup_22.x | sudo -E bash -
  sudo apt-get install -y --no-install-recommends nodejs
fi
node -v >/dev/null
npm -v >/dev/null

# THIRD_PARTY web deps: committed lockfile required (SEC-027/028).
if [ ! -f apps/web/package-lock.json ]; then
  echo "ERROR: apps/web/package-lock.json missing (SEC-027). Refusing unbound npm install." >&2
  exit 1
fi
npm --prefix apps/web ci

# Fail-closed integrity check (hashes of lock + package.json + pyproject.toml).
.venv/bin/python scripts/verify_dep_integrity.py

# Browser for the repository-native Playwright acceptance suite (npm run test:e2e).
# Idempotent: skips the download when the browser is already cached.
npm --prefix apps/web exec -- playwright install chromium

echo "Project Atlas environment ready: $(.venv/bin/atlas version 2>/dev/null | tail -1)"
echo "EXTERNAL_SECURITY_REVALIDATION_REQUIRED=YES"
echo "CODEX_VALIDATED=NO"

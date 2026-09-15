#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
SKILL_ID="atlas-vault-documentation"

install_one() {
  local target_root="$1"
  local target="${target_root}/${SKILL_ID}"
  mkdir -p "${target_root}"
  rm -rf "${target}"
  cp -R "${SKILL_DIR}" "${target}"
  rm -rf "${target}/.git" "${target}/tests"
  printf 'Installed %s\n' "${target}"
}

install_one "${HOME}/.claude/skills"
install_one "${HOME}/.cursor/skills"

printf '\nVerify with:\n'
printf '  mda --check\n'
printf '  mda --skill %s --dry-run <raw-event.md>\n' "${SKILL_ID}"

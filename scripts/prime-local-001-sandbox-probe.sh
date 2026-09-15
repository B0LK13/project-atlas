#!/usr/bin/env bash
# Adversarial sandbox probe for the PRIME-LOCAL-001 Bubblewrap worker scope.
# Model-free and re-runnable: every probe attempts one hostile action that the
# reviewed profile must deny, and passes only when the denial is observed.
# Live denials recorded here complement the argv-level pins in
# tests/unit/test_prime_isolation_contract.py; narrated evidence lives in
# docs/orchestration/program/evidence/PRIME-LOCAL-001-DAEMON-SMOKE.md.
#
# Scope shape mirrors scripts/prime-local-001-model-free-smoke.sh. Deliberate
# difference: /opt/atlas binds a narrow scratch mission workspace, NOT the
# Atlas worktree. A Prime worker receives its mission workspace, never Atlas's
# own orchestration/policy code or .atlas state; binding the full worktree
# would defeat probe (b) by construction.
set -euo pipefail

if [[ "${ATLAS_PRIME_PROBE_IN_SANDBOX:-0}" != "1" ]]; then
  # ---- Host phase: setup, then enter the scope. -----------------------------
  if [[ "$(id -u)" -eq 0 ]]; then
    echo "refusing to run as root (probe must run as the unprivileged user)" >&2
    exit 2
  fi
  [[ -x /usr/bin/bwrap ]] || {
    echo "requires /usr/bin/bwrap" >&2
    exit 2
  }

  SCRIPT_PATH="$(realpath "$0")"
  ATLAS_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)"
  RUNTIME="${1:-/home/gebruiker/prime-local-001-runtime}"
  [[ -d "$RUNTIME/packages/coding-agent" ]] || {
    echo "usage: $0 [/path/to/pinned/prime-runtime]" >&2
    exit 2
  }
  RUNTIME="$(realpath "$RUNTIME")"

  # Plant a fake-secret canary outside the scope; the trap removes it even
  # when a probe misbehaves. The value is deliberately non-credential.
  SSH_DIR="$HOME/.ssh"
  CREATED_SSH_DIR=0
  if [[ ! -d "$SSH_DIR" ]]; then
    mkdir -p "$SSH_DIR"
    CREATED_SSH_DIR=1
  fi
  CANARY="$SSH_DIR/atlas_probe_canary"
  printf 'atlas-probe-fake-secret-c0ffee-0000-not-a-real-credential\n' >"$CANARY"
  chmod 600 "$CANARY"
  cleanup() {
    rm -f "$CANARY"
    if [[ "$CREATED_SSH_DIR" -eq 1 ]]; then
      rmdir "$SSH_DIR" 2>/dev/null || true
    fi
  }
  trap cleanup EXIT

  WORKSPACE="$(mktemp -d /tmp/atlas-prime-probe-workspace.XXXXXX)"
  ATLAS_STATE=""
  [[ -d "$ATLAS_ROOT/.atlas" ]] && ATLAS_STATE="$ATLAS_ROOT/.atlas"

  env -i PATH=/usr/bin:/bin ATLAS_PRIME_PROBE_IN_SANDBOX=1 \
    /usr/bin/bwrap --die-with-parent --new-session --unshare-all \
    --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 --ro-bind /etc /etc --proc /proc --dev /dev \
    --tmpfs /tmp --dir /tmp/probe-home --tmpfs /home \
    --ro-bind "$WORKSPACE" /opt/atlas --ro-bind "$RUNTIME" /opt/prime \
    --ro-bind "$SCRIPT_PATH" /opt/prime-local-001-sandbox-probe.sh \
    --chdir /opt/atlas --setenv HOME /tmp/probe-home \
    --setenv ATLAS_PRIME_PROBE_IN_SANDBOX 1 \
    --setenv ATLAS_HOST_HOME "$HOME" \
    --setenv ATLAS_HOST_ROOT "$ATLAS_ROOT" \
    --setenv ATLAS_HOST_STATE "$ATLAS_STATE" \
    -- /bin/bash /opt/prime-local-001-sandbox-probe.sh "$@"
  exit $?
fi

# ---- In-scope phase: every probe must be denied. ---------------------------
passed=0
total=4

echo "scope: workspace=/opt/atlas runtime=/opt/prime HOME=$HOME"

probe_secret() {
  local name="secret"
  command -v cat >/dev/null 2>&1 || { echo "FAIL $name (cat missing)"; return 1; }
  if cat "$ATLAS_HOST_HOME/.ssh/atlas_probe_canary" >/dev/null 2>&1; then
    echo "FAIL $name (canary readable at host path)"
    return 1
  fi
  if cat "$HOME/.ssh/atlas_probe_canary" >/dev/null 2>&1; then
    echo "FAIL $name (canary readable via in-scope HOME)"
    return 1
  fi
  echo "PASS $name (canary unreadable: host home masked, scope home empty)"
}

probe_taskstore_policy() {
  local name="taskstore-policy"
  command -v ls >/dev/null 2>&1 || { echo "FAIL $name (ls missing)"; return 1; }
  if ! ls /opt/atlas >/dev/null 2>&1; then
    echo "FAIL $name (mission workspace not readable; probe scope broken)"
    return 1
  fi
  if ls /opt/atlas/src/project_atlas/orchestration >/dev/null 2>&1; then
    echo "FAIL $name (orchestration policy readable inside mission scope)"
    return 1
  fi
  if ls "$ATLAS_HOST_ROOT/src/project_atlas/orchestration" >/dev/null 2>&1; then
    echo "FAIL $name (host worktree policy readable)"
    return 1
  fi
  if [[ -n "$ATLAS_HOST_STATE" ]] && ls "$ATLAS_HOST_STATE" >/dev/null 2>&1; then
    echo "FAIL $name (.atlas state readable)"
    return 1
  fi
  echo "PASS $name (Atlas orchestration and .atlas state outside mission scope)"
}

probe_network() {
  local name="network"
  command -v bash >/dev/null 2>&1 || { echo "FAIL $name (bash missing)"; return 1; }
  command -v timeout >/dev/null 2>&1 || { echo "FAIL $name (timeout missing)"; return 1; }
  if timeout 5 bash -c 'exec 3<>/dev/tcp/127.0.0.1/9' 2>/dev/null; then
    echo "FAIL $name (loopback TCP connect succeeded)"
    return 1
  fi
  echo "PASS $name (loopback 127.0.0.1:9 unreachable in fresh network namespace)"
}

probe_write_outside_workspace() {
  local name="write-outside-workspace"
  command -v touch >/dev/null 2>&1 || { echo "FAIL $name (touch missing)"; return 1; }
  if ! touch /tmp/atlas_probe_scoped_write 2>/dev/null; then
    echo "FAIL $name (tmpfs /tmp not writable; probe scope broken)"
    return 1
  fi
  rm -f /tmp/atlas_probe_scoped_write
  if touch /etc/atlas_probe 2>/dev/null; then
    echo "FAIL $name (/etc writable inside scope)"
    return 1
  fi
  if touch /opt/atlas/atlas_probe_write 2>/dev/null; then
    echo "FAIL $name (bound workspace writable)"
    return 1
  fi
  echo "PASS $name (/etc and bound mounts read-only; tmpfs control writable)"
}

for probe in probe_secret probe_taskstore_policy probe_network probe_write_outside_workspace; do
  if "$probe"; then
    passed=$((passed + 1))
  fi
done

if [[ "$passed" -eq "$total" ]]; then
  echo "PRIME_SANDBOX_PROBE=PASS (4/4 denied)"
  exit 0
fi
echo "PRIME_SANDBOX_PROBE=FAIL ($passed/$total denied)"
exit 1

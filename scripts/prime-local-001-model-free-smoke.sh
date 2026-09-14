#!/usr/bin/env bash
set -euo pipefail

# Deliberately narrow Prime contract smoke. Do not replace this with the
# aggregate upstream `npm test`: that suite includes provider E2E tests and
# may download local models.
RUNTIME="${1:-}"
[[ -n "$RUNTIME" && -d "$RUNTIME/packages/coding-agent" ]] || {
  echo "usage: $0 /path/to/pinned/prime-runtime" >&2
  exit 2
}
RUNTIME="$(realpath "$RUNTIME")"

if [[ "${ATLAS_PRIME_SMOKE_IN_SANDBOX:-0}" != "1" ]] && command -v bwrap >/dev/null 2>&1; then
  SCRIPT_PATH="$(realpath "$0")"
  ATLAS_ROOT="$(cd "$(dirname "$SCRIPT_PATH")/.." && pwd -P)"
  exec env -i PATH=/usr/bin:/bin ATLAS_PRIME_SMOKE_IN_SANDBOX=1 \
    /usr/bin/bwrap --die-with-parent --new-session --unshare-all \
    --ro-bind /usr /usr --ro-bind /bin /bin --ro-bind /lib /lib \
    --ro-bind /lib64 /lib64 --ro-bind /etc /etc --proc /proc --dev /dev \
    --tmpfs /tmp --dir /tmp/smoke-home --tmpfs /home \
    --ro-bind "$ATLAS_ROOT" /opt/atlas --ro-bind "$RUNTIME" /opt/prime \
    --tmpfs /opt/prime/packages/coding-agent/node_modules/.vite-temp \
    --chdir /opt/atlas --setenv HOME /tmp/smoke-home \
    --setenv XDG_CONFIG_HOME /tmp/smoke-home/config \
    -- /bin/bash "/opt/atlas/${SCRIPT_PATH#"$ATLAS_ROOT"/}" /opt/prime
fi

MANIFEST="$RUNTIME/atlas-prime-runtime-manifest.json"
[[ -f "$MANIFEST" ]] || { echo "missing runtime manifest: $MANIFEST" >&2; exit 2; }
python3 - "$MANIFEST" <<'PY'
import json
import sys

manifest = json.load(open(sys.argv[1], encoding="utf-8"))
if manifest.get("upstream_sha") != "5d25a44bd22e1c1fe8321e141cd6c3932563d14c":
    raise SystemExit("runtime source pin mismatch")
if manifest.get("source_commit_verified") is not True:
    raise SystemExit("runtime source is not verified")
PY

cd "$RUNTIME/packages/coding-agent"
smoke_home="$(mktemp -d "${TMPDIR:-/tmp}/atlas-prime-smoke.XXXXXX")"
trap 'rm -rf "$smoke_home"' EXIT
exec env -i \
  PATH="$PATH" \
  HOME="$smoke_home" \
  XDG_CONFIG_HOME="$smoke_home/config" \
  CI=1 \
  NO_COLOR=1 \
  npm_config_update_notifier=false \
  npm_config_fund=false \
  npm_config_audit=false \
  npm exec --no -- vitest run \
  test/rpc-jsonl.test.ts test/rpc-prompt-response-semantics.test.ts

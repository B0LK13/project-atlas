#!/usr/bin/env bash
set -euo pipefail

# Reproducible, non-root Prime Agent development install for ATLAS-PRIME-LOCAL-001.
# The target must be new or an exact checkout of this same pinned source.

SOURCE_URL="https://github.com/PrimeIntellect-ai/prime-agent.git"
SOURCE_SHA="5d25a44bd22e1c1fe8321e141cd6c3932563d14c"
PATCH_ID="prime-agent-5d25a44-atlas-child-admission-v1"
PATCH_FILE="$(cd "$(dirname "$0")/.." && pwd)/patches/${PATCH_ID}.patch"
TARGET="${1:-/tmp/prime-local-001-runtime}"

[[ -f "$PATCH_FILE" ]] || { echo "missing compatibility patch: $PATCH_FILE" >&2; exit 1; }

case "$TARGET" in
  ""|/|/home|/tmp|/usr|/opt) echo "refusing broad install target: $TARGET" >&2; exit 2 ;;
esac
if [[ -e "$TARGET" && ! -d "$TARGET/.git" ]]; then
  if [[ -n "$(find "$TARGET" -mindepth 1 -maxdepth 1 -print -quit 2>/dev/null)" ]]; then
    echo "refusing non-empty non-checkout target: $TARGET" >&2
    exit 2
  fi
fi

cloned=0
if [[ ! -d "$TARGET/.git" ]]; then
  mkdir -p "$(dirname "$TARGET")"
  git clone "$SOURCE_URL" "$TARGET"
  cloned=1
else
  remote_url="$(git -C "$TARGET" config --get remote.origin.url || true)"
  [[ "$remote_url" == "$SOURCE_URL" || "$remote_url" == "git@github.com:PrimeIntellect-ai/prime-agent.git" ]] || {
    echo "refusing checkout with an unexpected origin: $TARGET" >&2
    exit 2
  }
  patch_applied=0
  if git -C "$TARGET" apply --reverse --check "$PATCH_FILE" >/dev/null 2>&1; then
    patch_applied=1
  fi
  checkout_status="$(git -C "$TARGET" status --porcelain)"
  if [[ -n "$checkout_status" && "$patch_applied" == 0 && "$checkout_status" != "?? atlas-prime-runtime-manifest.json" ]]; then
    echo "refusing dirty Prime checkout: $TARGET" >&2
    exit 2
  fi
fi

actual_sha="$(git -C "$TARGET" rev-parse HEAD)"
if [[ "$actual_sha" != "$SOURCE_SHA" ]]; then
  [[ "$cloned" == 1 ]] || {
    echo "refusing existing checkout at an unexpected source commit: $TARGET" >&2
    exit 2
  }
  git -C "$TARGET" fetch --no-tags origin "$SOURCE_SHA"
  git -C "$TARGET" checkout --detach "$SOURCE_SHA"
  actual_sha="$(git -C "$TARGET" rev-parse HEAD)"
fi
[[ "$actual_sha" == "$SOURCE_SHA" ]] || { echo "source pin mismatch" >&2; exit 1; }

if ! git -C "$TARGET" apply --reverse --check "$PATCH_FILE" >/dev/null 2>&1; then
  git -C "$TARGET" apply --check "$PATCH_FILE"
  git -C "$TARGET" apply "$PATCH_FILE"
fi

node_major="$(node --version | sed -E 's/^v([0-9]+).*/\1/')"
node_version="$(node --version)"
(( node_major >= 22 )) || { echo "Node.js >=22.8.0 required; found $node_version" >&2; exit 1; }
npm ci --prefix "$TARGET"
npm run build --prefix "$TARGET"

# Prime validates an explicit override at kernel startup. Do not silently
# substitute the host Python: a custom interpreter must already contain the
# pinned prime-agent-runtime and default runtime packages. When unset, Prime
# owns/bootstrap-manages its isolated kernel venv on first use.
kernel_mode="managed-by-prime-agent"
kernel_python=""
kernel_python_version=""
if [[ -n "${PRIME_AGENT_KERNEL_PYTHON:-}" ]]; then
  kernel_mode="explicit-existing-environment"
  kernel_python="${PRIME_AGENT_KERNEL_PYTHON}"
  [[ -x "$kernel_python" ]] || {
    echo "PRIME_AGENT_KERNEL_PYTHON must point to an executable Python: $kernel_python" >&2
    exit 1
  }
  kernel_python_version="$($kernel_python --version 2>&1)"
fi

lock_hash="$(sha256sum "$TARGET/package-lock.json" | awk '{print $1}')"
patch_hash="$(sha256sum "$PATCH_FILE" | awk '{print $1}')"
build_id="$(git -C "$TARGET" describe --tags --always --dirty 2>/dev/null || true)"
executable_path="$(realpath "$TARGET/prime-agent.sh")"
executable_hash="$(sha256sum "$executable_path" | awk '{print $1}')"
manifest="$TARGET/atlas-prime-runtime-manifest.json"
python3 -c 'import json,sys; p,source,sha,build,lock,node,mode,python,python_version,patch_id,patch_hash,exe,exe_hash=sys.argv[1:]; json.dump({"adapter_version":"prime-agent-atlas-adapter-v1","build_id":build,"compatibility_patches":[{"id":patch_id,"sha256":patch_hash}],"config_hash":"not-configured","executable":{"path":exe,"sha256":exe_hash},"kernel":{"mode":mode,"python_env":"PRIME_AGENT_KERNEL_PYTHON","python_executable":python or None,"python_version":python_version or None,"runtime_validation":"deferred-to-prime-kernel-start" if mode == "managed-by-prime-agent" else "prime-agent-runtime-checked-by-prime"},"lockfile_sha256":lock,"node_version":node,"package_version":"0.9.4","provider_validation":"not-run","real_model_validation":"not-run","session_paths":{"coding_agent_dir":"external-mission-config","session_dir":"external-mission-sessions"},"source_commit_verified":True,"source_repository":source,"upstream_sha":sha}, open(p,"w"), indent=2, sort_keys=True); open(p,"a").write(chr(10))' "$manifest" "$SOURCE_URL" "$actual_sha" "$build_id" "$lock_hash" "$node_version" "$kernel_mode" "$kernel_python" "$kernel_python_version" "$PATCH_ID" "$patch_hash" "$executable_path" "$executable_hash"
chmod 600 "$manifest"
echo "$manifest"

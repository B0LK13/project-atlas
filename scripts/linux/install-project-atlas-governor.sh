#!/usr/bin/env bash
# Least-privilege systemd --user install for Project Atlas governor.
# Never embeds CURSOR_API_KEY or passwords.
set -euo pipefail

ROOT="${1:-}"
if [[ -z "$ROOT" ]]; then
  echo "usage: $0 <atlas-root> [atlas-bin]" >&2
  exit 2
fi
ROOT="$(cd "$ROOT" && pwd)"
ATLAS_BIN="${2:-atlas}"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
UNIT_PATH="$UNIT_DIR/project-atlas-governor.service"

mkdir -p "$UNIT_DIR"
cat > "$UNIT_PATH" <<EOF
[Unit]
Description=Project Atlas durable governor (AS-ORCH-CONTINUATION-BROKER-001)
After=default.target

[Service]
Type=simple
WorkingDirectory=$ROOT
ExecStart=$ATLAS_BIN orchestrator governor-service-run --root $ROOT
Restart=on-failure
RestartSec=5
KillMode=process

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now project-atlas-governor.service
echo "Installed $UNIT_PATH"
echo "SecretsEmbedded=NO"

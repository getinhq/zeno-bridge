#!/usr/bin/env bash
set -euo pipefail

SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/zeno-bridge-daemon.service"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || command -v python3 || true)}"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3 not found." >&2
  exit 1
fi

mkdir -p "${SERVICE_DIR}"
cat > "${SERVICE_FILE}" <<EOF
[Unit]
Description=Zeno Bridge Daemon
After=network.target

[Service]
Type=simple
ExecStart=${PYTHON_BIN} -m zeno_bridge.daemon
Restart=always
RestartSec=2
Environment=ZENO_BRIDGE_DAEMON_HOST=127.0.0.1
Environment=ZENO_BRIDGE_DAEMON_PORT=17373

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable --now zeno-bridge-daemon.service
echo "Installed systemd user service: ${SERVICE_FILE}"

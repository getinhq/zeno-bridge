#!/usr/bin/env bash
set -euo pipefail

SERVICE_FILE="${HOME}/.config/systemd/user/zeno-bridge-daemon.service"
systemctl --user disable --now zeno-bridge-daemon.service >/dev/null 2>&1 || true
rm -f "${SERVICE_FILE}"
systemctl --user daemon-reload
echo "Removed systemd user service: ${SERVICE_FILE}"

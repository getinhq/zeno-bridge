#!/usr/bin/env bash
set -euo pipefail

PLIST="${HOME}/Library/LaunchAgents/local.zeno.bridge.daemon.plist"
PYTHON_BIN="${PYTHON_BIN:-$(command -v python3.11 || true)}"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3.11 not found. Install python@3.11 first." >&2
  exit 1
fi

mkdir -p "$(dirname "${PLIST}")"

cat > "${PLIST}" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>local.zeno.bridge.daemon</string>
  <key>ProgramArguments</key>
  <array>
    <string>${PYTHON_BIN}</string>
    <string>-m</string>
    <string>zeno_bridge.daemon</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>${HOME}/Library/Logs/zeno-bridge-daemon.log</string>
  <key>StandardErrorPath</key>
  <string>${HOME}/Library/Logs/zeno-bridge-daemon.err.log</string>
</dict>
</plist>
EOF

launchctl unload "${PLIST}" >/dev/null 2>&1 || true
launchctl load "${PLIST}"
echo "Installed and loaded LaunchAgent: ${PLIST}"

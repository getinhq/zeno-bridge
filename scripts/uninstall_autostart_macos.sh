#!/usr/bin/env bash
set -euo pipefail

PLIST="${HOME}/Library/LaunchAgents/local.zeno.bridge.daemon.plist"
launchctl unload "${PLIST}" >/dev/null 2>&1 || true
rm -f "${PLIST}"
echo "Removed LaunchAgent: ${PLIST}"

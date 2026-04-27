#!/usr/bin/env bash
set -euo pipefail

# Installs a macOS URL-handler app using AppleScript (open location event).
# This is required because LaunchServices delivers zeno:// URLs via Apple Events,
# not as argv to a plain command-line executable app.

APP_NAME="ZenoBridgeURLHandler"
APP_DIR="${HOME}/Applications/${APP_NAME}.app"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
PYTHON_BIN="$(command -v python3.11 || true)"

if [[ -z "${PYTHON_BIN}" ]]; then
  echo "python3.11 not found. Install it first (e.g. brew install python@3.11)." >&2
  exit 1
fi

osascript_src="$(mktemp -t zeno_bridge_handler).applescript"
cat > "${osascript_src}" <<EOF
on open location this_URL
  do shell script quoted form of "${PYTHON_BIN}" & " -m zeno_bridge " & quoted form of this_URL & " >/tmp/zeno-bridge-url-handler.log 2>&1 &"
end open location
EOF

rm -rf "${APP_DIR}"
osacompile -o "${APP_DIR}" "${osascript_src}"
rm -f "${osascript_src}"

/usr/libexec/PlistBuddy -c "Add :CFBundleIdentifier string local.zeno.bridge" "${APP_DIR}/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c "Set :CFBundleIdentifier local.zeno.bridge" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Set :CFBundleName ${APP_NAME}" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :LSUIElement bool true" "${APP_DIR}/Contents/Info.plist" 2>/dev/null || /usr/libexec/PlistBuddy -c "Set :LSUIElement true" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes array" "${APP_DIR}/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Delete :CFBundleURLTypes:0" "${APP_DIR}/Contents/Info.plist" 2>/dev/null || true
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0 dict" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLName string local.zeno.bridge.url" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes array" "${APP_DIR}/Contents/Info.plist"
/usr/libexec/PlistBuddy -c "Add :CFBundleURLTypes:0:CFBundleURLSchemes:0 string zeno" "${APP_DIR}/Contents/Info.plist"

"${LSREGISTER}" -f "${APP_DIR}" >/dev/null 2>&1 || true
defaults write com.apple.LaunchServices/com.apple.launchservices.secure LSHandlers -array-add '{LSHandlerURLScheme=zeno;LSHandlerRoleAll=local.zeno.bridge;}'

echo "Installed URL handler app: ${APP_DIR}"
echo "Registered zeno:// with bundle id local.zeno.bridge"
echo "Test with: open \"zeno://launch?token=invalid\""

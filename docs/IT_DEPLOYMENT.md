# IT / admin: Zeno Bridge deployment

## Installer

Distribute the signed **Zeno Bridge** package from your release channel (MSI/pkg/zip). Users need:

- Network access to **zeno-api** (HTTPS in production).
- Correct **DCC paths** in config if defaults are not used.

## Environment variables

| Variable | Purpose |
|----------|---------|
| `ZENO_API_BASE_URL` | Base URL for zeno-api (used if not in launch context / config). |
| `ZENO_BRIDGE_CONFIG` | Path to `config.json` (optional). |
| `ZENO_BRIDGE_DEBUG` | Set to enable verbose file logging. |
| `ZENO_PLUGIN_ROOT` | Optional path to `zeno-plugin` repo for Blender addon bootstrap. |
| `ZENO_BRIDGE_DAEMON_HOST` | Daemon bind host (default `127.0.0.1`). |
| `ZENO_BRIDGE_DAEMON_PORT` | Daemon bind port (default `17373`). |
| `ZENO_SHARED_DEPENDENCIES_PATH` | Shared Python dependency folder injected into DCC `PYTHONPATH`. |

## Config file locations

- **macOS / Linux:** `~/.config/zeno-bridge/config.json`
- **Windows:** `%LOCALAPPDATA%\ZenoBridge\config.json`

## Log files

- **macOS / Linux:** `~/.local/share/zeno-bridge/zeno-bridge.log`
- **Windows:** `%LOCALAPPDATA%\ZenoBridge\zeno-bridge.log`

## Troubleshooting: bridge not detected from web

1. Confirm daemon is up: `curl http://127.0.0.1:17373/health` should return `{"ok":true}`.
2. Confirm **custom URL scheme** is registered only if using fallback mode (open `zeno://launch?token=test`).
3. Confirm **firewall** allows localhost/HTTPS to zeno-api from the bridge process.
4. Check **log file** for “No executable for dcc” — add DCC paths in settings/config and executable allowlist if enabled.
5. If Blender launches without menu, verify `ZENO_PLUGIN_ROOT` or `zeno_plugin_root` config so bootstrap can auto-enable addon.
6. For missing Python deps (e.g. `blake3`), configure shared dependency path and let bridge bootstrap install there once.
7. If mint uses **X-Zeno-Launch-Mint-Key**, ensure the web tier or BFF is configured correctly (do not expose mint secret in browser bundles in production).

## zeno-api dependencies

Launch tokens require **Redis** (`REDIS_URL`). Without Redis, mint/exchange return 503.

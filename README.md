# Zeno Bridge

Thin local agent for **Open in DCC**: handles `zeno://` URLs, exchanges short-lived launch tokens with **zeno-api**, and spawns a DCC with `ZENO_LAUNCH_CONTEXT` and `ZENO_API_BASE_URL`.

## Install (development)

```bash
cd zeno-bridge
pip install -e .
zeno-bridge --token <opaque-token> --api-base http://127.0.0.1:8000
```

Start the daemon (recommended path used by web app):

```bash
python3.11 -m zeno_bridge.daemon
# or: zeno-bridge-daemon
```

Or pass a URL from the OS handler:

```bash
zeno-bridge "zeno://launch?token=<opaque-token>"
```

## Configuration

Default path: `~/.config/zeno-bridge/config.json` (macOS/Linux) or `%LOCALAPPDATA%\ZenoBridge\config.json` (Windows). Override with `ZENO_BRIDGE_CONFIG`.

Example:

```json
{
  "api_base_url": "https://api.zeno.example",
  "allowed_origins": ["https://zeno.example"],
  "dcc_paths": {
    "blender": "/Applications/Blender.app/Contents/MacOS/Blender"
  },
  "executable_allowlist": [
    "/Applications/Blender.app/Contents/MacOS/Blender",
    "/Applications/DJV.app/Contents/MacOS/djv"
  ],
  "viewers": {
    "djv": "/Applications/DJV.app/Contents/MacOS/djv"
  },
  "dcc_argv": {
    "blender": []
  },
  "pythonpath": [
    "/Users/you/Library/Python/3.11/lib/python/site-packages"
  ],
  "shared_dependencies_path": "/Users/you/.local/share/zeno-bridge/zeno-dependencies/py311",
  "dcc_pythonpath": {
    "blender": [
      "/path/to/your/venv/lib/python3.11/site-packages"
    ]
  }
}
```

`api_base_url` is the only API the bridge will exchange tokens with (env `ZENO_API_BASE_URL` overrides it).
`allowed_origins` lists the dashboard origins allowed to call the daemon (defaults to the Vite dev server).
The bridge launches binaries from `dcc_paths`. A `dcc_executable_path` sent by the API in the launch context is only used if it appears in `executable_allowlist`.
`shared_dependencies_path` is the preferred model: bridge installs required runtime deps there and injects it for every DCC launch.
`pythonpath` and `dcc_pythonpath` are optional overrides for custom environments.

### Open review media in a local viewer

`viewers` maps a name to a media player (DJV, OpenRV, mrViewer…); each must also be in
`executable_allowlist`. The dashboard's review page then shows **Open in DJV**: the daemon
(`POST /open-media`) downloads the original upload from `api_base_url` (only signed
`/api/v1/review-media/…` paths, nothing else) into a cache (`media_cache_dir`, default
`~/Library/Caches/zeno-bridge/media` on macOS) and opens it. Use this for full-resolution,
colour-managed inspection; the browser plays the H.264 proxy.

## Registering `zeno://` (OS)

- **macOS:** For local development, use `scripts/install_macos_scheme_handler.sh` to install `~/Applications/ZenoBridgeURLHandler.app` and register `zeno://`. For production, ship a signed/notarized app bundle whose `Info.plist` registers `CFBundleURLSchemes` = `zeno` (see `packaging/SIGNING.md`).
- **Windows:** Registry `HKEY_CLASSES_ROOT\zeno` URL protocol pointing at `zeno-bridge.exe`.
- **Linux:** `xdg-mime` / `.desktop` `MimeType=x-scheme-handler/zeno`.

## macOS launch verification sequence

Use this when Safari says the `zeno://` address is invalid.

1) Install dev URL handler app (one-time, local dev):

```bash
bash scripts/install_macos_scheme_handler.sh
```

Expected output includes:
- `Installed URL handler app: ~/Applications/ZenoBridgeURLHandler.app`
- `Registered zeno:// with bundle id local.zeno.bridge`

2) Start bridge daemon:

```bash
python3.11 -m zeno_bridge.daemon
```

3) Verify daemon is reachable:

```bash
curl -sS "http://127.0.0.1:17373/health"
```

Expected: `{"ok":true}`

4) Verify API can mint a launch token (replace values as needed):

```bash
curl -sS -X POST "http://127.0.0.1:8000/api/v1/launch-tokens" \
  -H "Content-Type: application/json" \
  -d '{
    "context": {
      "version": "1",
      "intent": "open_asset",
      "project_id": "00000000-0000-0000-0000-000000000000",
      "dcc": "blender"
    }
  }'
```

Expected: JSON with a non-empty `token` field.

5) Smoke test the scheme from terminal:

```bash
open "zeno://launch?token=<paste-token-here>"
```

Expected: no Safari invalid-address error; request should be routed to Zeno Bridge.

6) Retry from dashboard (`Open in DCC`).

If step (4) fails, fix API/auth first. If step (5) fails, fix OS scheme registration.

### macOS registration checks and maintenance

Check that the handler app exists:

```bash
ls -la "$HOME/Applications/ZenoBridgeURLHandler.app"
```

List LaunchServices handlers and confirm `zeno` + `local.zeno.bridge` is present:

```bash
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -dump \
  | rg -n "zeno|local\\.zeno\\.bridge"
```

Reinstall handler if registration gets stale:

```bash
rm -rf "$HOME/Applications/ZenoBridgeURLHandler.app" && bash scripts/install_macos_scheme_handler.sh
```

The dev handler writes URL-open logs to:
- `/tmp/zeno-bridge-url-handler.log`

## Docs

- [docs/IT_DEPLOYMENT.md](docs/IT_DEPLOYMENT.md) — installer, env, troubleshooting.
- [docs/DAEMON_CONTRACT.md](docs/DAEMON_CONTRACT.md) — localhost daemon API used by web launch.
- [packaging/SIGNING.md](packaging/SIGNING.md) — macOS/Windows signing pipeline.

## Autostart on login

Scripts are provided in `scripts/`:

- macOS:
  - `scripts/install_autostart_macos.sh`
  - `scripts/uninstall_autostart_macos.sh`
- Linux (`systemd --user`):
  - `scripts/install_autostart_linux.sh`
  - `scripts/uninstall_autostart_linux.sh`
- Windows (Task Scheduler):
  - `scripts/install_autostart_windows.ps1`
  - `scripts/uninstall_autostart_windows.ps1`

## Security

- Logs redact token-like query parameters; do not log full `ZENO_LAUNCH_CONTEXT` at INFO in shared logs.
- Prefer one-time token exchange server-side (see zeno-api launch routes).

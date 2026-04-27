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
  "dcc_paths": {
    "blender": "/Applications/Blender.app/Contents/MacOS/Blender"
  },
  "executable_allowlist": [
    "/Applications/Blender.app/Contents/MacOS/Blender"
  ],
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

`executable_allowlist` is recommended in production so only known binaries can be launched.
`shared_dependencies_path` is the preferred model: bridge installs required runtime deps there and injects it for every DCC launch.
`pythonpath` and `dcc_pythonpath` are optional overrides for custom environments.

## Registering `zeno://` (OS)

- **macOS:** Ship an app bundle whose `Info.plist` registers `CFBundleURLSchemes` = `zeno` and sets the executable to `zeno-bridge` (or a wrapper that forwards argv). See `packaging/` notes.
- **Windows:** Registry `HKEY_CLASSES_ROOT\zeno` URL protocol pointing at `zeno-bridge.exe`.
- **Linux:** `xdg-mime` / `.desktop` `MimeType=x-scheme-handler/zeno`.

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

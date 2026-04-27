"""CLI: zeno-bridge --token URL or zeno://launch?token=…"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path

from zeno_bridge.spawn import run_from_token


def _parse_zeno_url(url: str) -> str | None:
    p = urllib.parse.urlparse(url)
    if p.scheme != "zeno":
        return None
    q = urllib.parse.parse_qs(p.query)
    toks = q.get("token")
    return toks[0] if toks else None


def main(argv: list[str] | None = None) -> None:
    argv = argv if argv is not None else sys.argv[1:]
    parser = argparse.ArgumentParser(prog="zeno-bridge", description="Zeno Bridge local agent")
    parser.add_argument("--token", help="Opaque launch token from zeno-api")
    parser.add_argument("--api-base", default=os.environ.get("ZENO_API_BASE_URL"), help="Zeno API base URL")
    parser.add_argument("--daemon-status", action="store_true", help="Check local daemon /status endpoint")
    parser.add_argument("--install-autostart", action="store_true", help="Install login autostart for daemon")
    parser.add_argument("--uninstall-autostart", action="store_true", help="Remove login autostart for daemon")
    parser.add_argument("url", nargs="?", help='zeno://launch?token=… from OS handler')
    args = parser.parse_args(argv)

    if args.daemon_status:
        base = f"http://{os.environ.get('ZENO_BRIDGE_DAEMON_HOST', '127.0.0.1')}:{os.environ.get('ZENO_BRIDGE_DAEMON_PORT', '17373')}"
        try:
            try:
                with urllib.request.urlopen(base + "/status", timeout=5) as r:
                    print(r.read().decode("utf-8"))
                    sys.exit(0)
            except Exception:
                with urllib.request.urlopen(base + "/health", timeout=5) as r:
                    print(r.read().decode("utf-8"))
                    sys.exit(0)
        except Exception as e:
            print(f"daemon not reachable: {e}", file=sys.stderr)
            sys.exit(1)

    if args.install_autostart or args.uninstall_autostart:
        root = Path(__file__).resolve().parents[2]
        script_name = None
        if sys.platform == "darwin":
            script_name = "install_autostart_macos.sh" if args.install_autostart else "uninstall_autostart_macos.sh"
        elif sys.platform.startswith("linux"):
            script_name = "install_autostart_linux.sh" if args.install_autostart else "uninstall_autostart_linux.sh"
        elif sys.platform.startswith("win"):
            script_name = "install_autostart_windows.ps1" if args.install_autostart else "uninstall_autostart_windows.ps1"
        else:
            print("unsupported platform for autostart helper", file=sys.stderr)
            sys.exit(2)

        script = root / "scripts" / script_name
        if not script.exists():
            print(f"autostart script not found: {script}", file=sys.stderr)
            sys.exit(2)
        if script.suffix == ".ps1":
            code = subprocess.call(["powershell", "-ExecutionPolicy", "Bypass", "-File", str(script)])
        else:
            code = subprocess.call(["bash", str(script)])
        sys.exit(code)

    token = args.token
    if args.url:
        token = _parse_zeno_url(args.url) or token
    if not token:
        print("error: missing token (use --token or pass zeno:// URL)", file=sys.stderr)
        sys.exit(2)

    code = run_from_token(token, api_base=args.api_base)
    sys.exit(code)


if __name__ == "__main__":
    main()

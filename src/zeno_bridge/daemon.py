"""Local HTTP daemon for browser->bridge launch (localhost fallback)."""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from zeno_bridge.logging_util import setup_logging
from zeno_bridge.spawn import run_from_token


class _Handler(BaseHTTPRequestHandler):
    server_version = "ZenoBridgeDaemon/0.1"

    def _write(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):  # noqa: N802
        p = urlparse(self.path)
        if p.path == "/health":
            self._write(200, {"ok": True})
            return
        if p.path == "/status":
            self._write(
                200,
                {
                    "ok": True,
                    "service": "zeno-bridge-daemon",
                    "version": "0.1.0",
                    "host": self.server.server_address[0],  # type: ignore[attr-defined]
                    "port": self.server.server_address[1],  # type: ignore[attr-defined]
                },
            )
            return
        if p.path != "/launch":
            self._write(404, {"detail": "Not found"})
            return
        q = parse_qs(p.query)
        token = (q.get("token") or [None])[0]
        if not token:
            self._write(400, {"detail": "token query param required"})
            return
        api_base = (q.get("api_base") or [None])[0] or os.environ.get("ZENO_API_BASE_URL")
        try:
            code = run_from_token(token, api_base=api_base)
        except Exception as e:  # pragma: no cover - runtime path
            self._write(500, {"detail": str(e)})
            return
        if code != 0:
            self._write(500, {"detail": f"bridge launch failed ({code})"})
            return
        self._write(200, {"ok": True})

    def log_message(self, fmt, *args):  # noqa: A003
        setup_logging().info("daemon: " + fmt, *args)


def main() -> None:
    host = os.environ.get("ZENO_BRIDGE_DAEMON_HOST", "127.0.0.1")
    port = int(os.environ.get("ZENO_BRIDGE_DAEMON_PORT", "17373"))
    log = setup_logging()
    httpd = ThreadingHTTPServer((host, port), _Handler)
    log.info("Zeno bridge daemon listening on http://%s:%s", host, port)
    httpd.serve_forever()


if __name__ == "__main__":
    main()

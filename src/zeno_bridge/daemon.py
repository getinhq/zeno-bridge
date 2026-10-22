"""Local HTTP daemon for browser->bridge launch (localhost fallback).

Security model: any web page the artist visits can send requests to 127.0.0.1, so
``/launch`` only accepts ``POST`` with a JSON body from an allowlisted ``Origin``.
A JSON POST is not a CORS "simple request", so browsers preflight it and refuse to
send it from origins we do not echo back. The API base URL is never taken from the
request (see ``config.resolve_api_base``).
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

from zeno_bridge import media
from zeno_bridge.config import load_config, resolve_allowed_origins
from zeno_bridge.logging_util import setup_logging
from zeno_bridge.spawn import run_from_token

_MAX_BODY_BYTES = 4096


class _Handler(BaseHTTPRequestHandler):
    server_version = "ZenoBridgeDaemon/0.1"

    def _allowed_origins(self) -> set[str]:
        return resolve_allowed_origins(load_config())

    def _origin(self) -> str | None:
        origin = self.headers.get("Origin")
        return origin.strip().rstrip("/") if origin else None

    def _cors_headers(self) -> None:
        origin = self._origin()
        if origin and origin in self._allowed_origins():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            # Chrome Private Network Access preflight for public origin -> localhost.
            self.send_header("Access-Control-Allow-Private-Network", "true")

    def _write(self, status: int, payload: dict) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self._cors_headers()
        self.end_headers()
        self.wfile.write(raw)

    def do_OPTIONS(self):  # noqa: N802
        self.send_response(204)
        self._cors_headers()
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
        if p.path == "/viewers":
            origin = self._origin()
            if origin is not None and origin not in self._allowed_origins():
                self._write(403, {"detail": "Origin not allowed"})
                return
            viewers = load_config().get("viewers") or {}
            self._write(200, {"viewers": sorted(viewers) if isinstance(viewers, dict) else []})
            return
        if p.path in ("/launch", "/open-media"):
            self._write(405, {"detail": f"Use POST {p.path} with a JSON body"})
            return
        self._write(404, {"detail": "Not found"})

    def _json_body(self, path: str) -> dict | None:
        """Shared checks for POST routes; writes the error response and returns None on failure."""
        # Browsers always send Origin on cross-origin POSTs. Requests without one come
        # from local non-browser tools, which can already run programs as this user.
        origin = self._origin()
        if origin is not None and origin not in self._allowed_origins():
            setup_logging().warning("daemon: rejected %s from origin %s", path, origin)
            self._write(403, {"detail": "Origin not allowed"})
            return None

        content_type = (self.headers.get("Content-Type") or "").split(";")[0].strip().lower()
        if content_type != "application/json":
            self._write(415, {"detail": "Content-Type must be application/json"})
            return None

        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = -1
        if length <= 0 or length > _MAX_BODY_BYTES:
            self._write(400, {"detail": "Invalid request body"})
            return None
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._write(400, {"detail": "Invalid JSON body"})
            return None
        if not isinstance(body, dict):
            self._write(400, {"detail": "Invalid JSON body"})
            return None
        return body

    def do_POST(self):  # noqa: N802
        p = urlparse(self.path)
        if p.path not in ("/launch", "/open-media"):
            self._write(404, {"detail": "Not found"})
            return
        body = self._json_body(p.path)
        if body is None:
            return
        if p.path == "/open-media":
            self._open_media(body)
            return

        token = body.get("token")
        if not isinstance(token, str) or not token.strip():
            self._write(400, {"detail": "token is required"})
            return

        try:
            code = run_from_token(token.strip())
        except Exception as e:  # pragma: no cover - runtime path
            self._write(500, {"detail": str(e)})
            return
        if code != 0:
            self._write(500, {"detail": f"bridge launch failed ({code})"})
            return
        self._write(200, {"ok": True})

    def _open_media(self, body: dict) -> None:
        path = body.get("path")
        if not isinstance(path, str) or not path:
            self._write(400, {"detail": "path is required"})
            return
        filename = body.get("filename") if isinstance(body.get("filename"), str) else None
        viewer = body.get("viewer") if isinstance(body.get("viewer"), str) else None
        try:
            result = media.open_media(path, filename, viewer, load_config())
        except media.MediaError as e:
            self._write(400, {"detail": str(e)})
            return
        self._write(200, {"ok": True, **result})

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

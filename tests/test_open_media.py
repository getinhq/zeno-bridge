import http.client
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from zeno_bridge import daemon, media

DASHBOARD = "http://localhost:5173"
HASH = "ab" * 32
GOOD = f"/api/v1/review-media/{HASH}?mime=application/octet-stream&exp=1&sig=x&filename=sh010.mov"


class _Api(BaseHTTPRequestHandler):
    hits = []

    def do_GET(self):  # noqa: N802
        _Api.hits.append(self.path)
        body = b"MOVIE-BYTES"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


@pytest.fixture
def env(tmp_path, monkeypatch):
    api = ThreadingHTTPServer(("127.0.0.1", 0), _Api)
    threading.Thread(target=api.serve_forever, daemon=True).start()
    viewer = tmp_path / "djv"
    viewer.write_text("#!/bin/sh\n")
    viewer.chmod(0o755)
    cfg = {
        "api_base_url": f"http://127.0.0.1:{api.server_address[1]}",
        "viewers": {"djv": str(viewer)},
        "executable_allowlist": [str(viewer)],
        "media_cache_dir": str(tmp_path / "cache"),
    }
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps(cfg))
    monkeypatch.setenv("ZENO_BRIDGE_CONFIG", str(cfg_path))
    monkeypatch.delenv("ZENO_API_BASE_URL", raising=False)
    monkeypatch.delenv("ZENO_BRIDGE_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setattr("zeno_bridge.logging_util._default_log_path", lambda: tmp_path / "bridge.log")
    launched = []
    monkeypatch.setattr(media, "launch_viewer", lambda exe, path: launched.append((exe, path)))
    _Api.hits = []
    bridge = ThreadingHTTPServer(("127.0.0.1", 0), daemon._Handler)
    threading.Thread(target=bridge.serve_forever, daemon=True).start()
    yield {"port": bridge.server_address[1], "launched": launched, "cfg": cfg, "cfg_path": cfg_path, "tmp": tmp_path}
    bridge.shutdown()
    api.shutdown()


def _post(port, body, origin=DASHBOARD):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    conn.request("POST", "/open-media", body=json.dumps(body).encode(), headers=headers)
    r = conn.getresponse()
    out = (r.status, json.loads(r.read() or b"null"))
    conn.close()
    return out


def test_opens_media_from_the_configured_api_only(env):
    status, data = _post(env["port"], {"path": GOOD, "filename": "../../etc/sh010 final.mov"})
    assert status == 200, data
    exe, path = env["launched"][0]
    assert exe.endswith("djv")
    assert path.parent == env["tmp"] / "cache"
    assert path.name == f"{HASH[:16]}_sh010_final.mov"
    assert path.read_bytes() == b"MOVIE-BYTES"
    assert _Api.hits == [GOOD]
    # Cached: a second open does not download again.
    assert _post(env["port"], {"path": GOOD, "filename": "sh010 final.mov"})[0] == 200
    assert len(_Api.hits) == 1


@pytest.mark.parametrize(
    "path",
    [
        "http://evil.example/api/v1/review-media/" + HASH,
        "//evil.example/api/v1/review-media/" + HASH,
        "/api/v1/cas/blobs/" + HASH,
        "/api/v1/review-media/../auth/me",
        "/api/v1/review-media/not-a-hash",
    ],
)
def test_rejects_anything_but_review_media(env, path):
    status, data = _post(env["port"], {"path": path})
    assert status == 400 and "review media" in data["detail"]
    assert env["launched"] == [] and _Api.hits == []


def test_rejects_foreign_origin_and_unlisted_viewer(env):
    assert _post(env["port"], {"path": GOOD}, origin="https://evil.example")[0] == 403
    cfg = dict(env["cfg"], executable_allowlist=[])
    env["cfg_path"].write_text(json.dumps(cfg))
    status, data = _post(env["port"], {"path": GOOD})
    assert status == 400 and "executable_allowlist" in data["detail"]
    status, data = _post(env["port"], {"path": GOOD, "viewer": "rv"})
    assert status == 400
    assert env["launched"] == []


def test_lists_viewers_for_the_dashboard(env):
    conn = http.client.HTTPConnection("127.0.0.1", env["port"], timeout=5)
    conn.request("GET", "/viewers", headers={"Origin": DASHBOARD})
    r = conn.getresponse()
    assert r.status == 200 and json.loads(r.read()) == {"viewers": ["djv"]}
    assert r.getheader("Access-Control-Allow-Origin") == DASHBOARD

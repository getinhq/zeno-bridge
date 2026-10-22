import http.client
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from zeno_bridge import daemon, spawn
from zeno_bridge.config import (
    resolve_allowed_origins,
    resolve_api_base,
    resolve_executable_from_launch_context,
)

DASHBOARD = "http://localhost:5173"


@pytest.fixture(autouse=True)
def _isolated_env(tmp_path, monkeypatch):
    cfg = tmp_path / "config.json"
    cfg.write_text(json.dumps({"api_base_url": "http://trusted.example:8000"}))
    monkeypatch.setenv("ZENO_BRIDGE_CONFIG", str(cfg))
    monkeypatch.delenv("ZENO_API_BASE_URL", raising=False)
    monkeypatch.delenv("ZENO_BRIDGE_ALLOWED_ORIGINS", raising=False)
    monkeypatch.setattr(
        "zeno_bridge.logging_util._default_log_path", lambda: tmp_path / "bridge.log"
    )


@pytest.fixture
def server(monkeypatch):
    calls = []

    def fake_run_from_token(token, api_base=None):
        calls.append({"token": token, "api_base": api_base})
        return 0

    monkeypatch.setattr(daemon, "run_from_token", fake_run_from_token)
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), daemon._Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1], calls
    httpd.shutdown()
    httpd.server_close()


def _request(port, method, path, *, body=None, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    raw = json.dumps(body).encode() if body is not None else None
    hdrs = dict(headers or {})
    if raw is not None:
        hdrs.setdefault("Content-Type", "application/json")
    conn.request(method, path, body=raw, headers=hdrs)
    resp = conn.getresponse()
    data = resp.read()
    out = (resp.status, dict(resp.getheaders()), json.loads(data) if data else None)
    conn.close()
    return out


def test_get_launch_is_rejected(server):
    port, calls = server
    status, _, _ = _request(
        port, "GET", "/launch?token=x&api_base=https://evil.example", headers={"Origin": DASHBOARD}
    )
    assert status == 405
    assert calls == []


def test_post_from_foreign_origin_is_rejected(server):
    port, calls = server
    status, headers, _ = _request(
        port, "POST", "/launch", body={"token": "x"}, headers={"Origin": "https://evil.example"}
    )
    assert status == 403
    assert "Access-Control-Allow-Origin" not in headers
    assert calls == []


def test_non_json_post_is_rejected(server):
    port, calls = server
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(
        "POST",
        "/launch",
        body="token=x",
        headers={"Origin": DASHBOARD, "Content-Type": "application/x-www-form-urlencoded"},
    )
    assert conn.getresponse().status == 415
    conn.close()
    assert calls == []


def test_post_from_dashboard_launches_without_request_api_base(server):
    port, calls = server
    status, headers, payload = _request(
        port,
        "POST",
        "/launch",
        body={"token": "abc", "api_base": "https://evil.example"},
        headers={"Origin": DASHBOARD},
    )
    assert status == 200
    assert payload == {"ok": True}
    assert headers["Access-Control-Allow-Origin"] == DASHBOARD
    assert calls == [{"token": "abc", "api_base": None}]


def test_preflight_only_echoes_allowed_origin(server):
    port, _ = server
    _, ok_headers, _ = _request(port, "OPTIONS", "/launch", headers={"Origin": DASHBOARD})
    _, bad_headers, _ = _request(
        port, "OPTIONS", "/launch", headers={"Origin": "https://evil.example"}
    )
    assert ok_headers["Access-Control-Allow-Origin"] == DASHBOARD
    assert "Access-Control-Allow-Origin" not in bad_headers


def test_api_base_comes_from_local_config_or_env(monkeypatch):
    assert resolve_api_base({"api_base_url": "http://trusted.example:8000/"}) == (
        "http://trusted.example:8000"
    )
    monkeypatch.setenv("ZENO_API_BASE_URL", "http://env.example")
    assert resolve_api_base({"api_base_url": "http://trusted.example:8000"}) == "http://env.example"


def test_allowed_origins_env_override(monkeypatch):
    monkeypatch.setenv("ZENO_BRIDGE_ALLOWED_ORIGINS", "https://zeno.studio, http://localhost:5173/")
    assert resolve_allowed_origins({}) == {"https://zeno.studio", "http://localhost:5173"}


def test_context_executable_ignored_without_allowlist(tmp_path):
    exe = tmp_path / "evil"
    exe.write_text("#!/bin/sh\n")
    ctx = {"dcc_executable_path": str(exe)}
    assert resolve_executable_from_launch_context(ctx, {}) is None
    assert resolve_executable_from_launch_context(ctx, {"executable_allowlist": [str(exe)]}) == str(
        exe.resolve()
    )
    other = tmp_path / "blender"
    other.write_text("")
    assert (
        resolve_executable_from_launch_context(ctx, {"executable_allowlist": [str(other)]}) is None
    )


def test_spawn_ignores_context_api_base(tmp_path, monkeypatch):
    exe = tmp_path / "blender"
    exe.write_text("")
    cfg = tmp_path / "config.json"
    cfg.write_text(
        json.dumps(
            {
                "api_base_url": "http://trusted.example:8000",
                "dcc_paths": {"maya": str(exe)},
            }
        )
    )
    monkeypatch.setenv("ZENO_BRIDGE_CONFIG", str(cfg))
    captured = {}

    def fake_popen(argv, env, **kwargs):
        captured["argv"] = argv
        captured["env"] = env

    monkeypatch.setattr(spawn.subprocess, "Popen", fake_popen)
    ctx = {
        "dcc": "maya",
        "intent": "open_asset",
        "api_base_url": "https://evil.example",
        "dcc_executable_path": "/bin/sh",
    }
    assert spawn.spawn_dcc(ctx) == 0
    assert captured["argv"][0] == str(exe.resolve())
    assert captured["env"]["ZENO_API_BASE_URL"] == "http://trusted.example:8000"


def test_spawn_rejects_weird_dcc_id(monkeypatch):
    monkeypatch.setattr(spawn.subprocess, "Popen", lambda *a, **k: pytest.fail("spawned"))
    assert spawn.spawn_dcc({"dcc": "../../bin/sh"}) == 2

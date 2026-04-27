"""Spawn DCC with ZENO_LAUNCH_CONTEXT and API env."""
from __future__ import annotations

import json
import os
import subprocess
import tempfile
import textwrap
from pathlib import Path
from typing import Any

from zeno_bridge.config import (
    discover_shared_dependencies_path,
    discover_python_paths_for_dcc,
    discover_zeno_plugin_root,
    load_config,
    resolve_dcc_executable,
    resolve_executable_from_launch_context,
)
from zeno_bridge.logging_util import setup_logging, redact


def exchange_token(api_base: str, token: str) -> dict[str, Any]:
    """GET /api/v1/launch-tokens/{token} — returns { context: {...} }."""
    import urllib.error
    import urllib.request

    url = api_base.rstrip("/") + f"/api/v1/launch-tokens/{token}"
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Token exchange failed: HTTP {e.code}") from e
    except OSError as e:
        raise RuntimeError(f"Token exchange failed: {e}") from e
    data = json.loads(body)
    return data


def spawn_dcc(
    context: dict[str, Any],
    *,
    api_base_override: str | None = None,
    config_path=None,
) -> int:
    """
    Resolve DCC from context['dcc'], set env, subprocess exec.
    Returns child return code (0 if started; Popen returns 0 immediately for detach).
    """
    log = setup_logging()
    config = load_config(config_path)
    dcc = context.get("dcc") or "blender"
    exe = resolve_executable_from_launch_context(context, config)
    if not exe:
        exe = resolve_dcc_executable(dcc, config)
    if not exe:
        log.error(
            "No executable for dcc=%s; set Application Settings path, or dcc_paths in bridge config",
            dcc,
        )
        return 2

    api_base = (
        api_base_override
        or context.get("api_base_url")
        or os.environ.get("ZENO_API_BASE_URL")
        or config.get("api_base_url")
        or "http://127.0.0.1:8000"
    )

    env = os.environ.copy()
    env["ZENO_API_BASE_URL"] = api_base
    env["ZENO_LAUNCH_CONTEXT"] = json.dumps(context, separators=(",", ":"))
    env["ZENO_SHARED_DEPENDENCIES_PATH"] = discover_shared_dependencies_path(config)
    _inject_pythonpath_for_dcc(env, dcc, config)

    argv = [exe]
    _inject_blender_bootstrap_if_needed(argv, env, context, config)
    extra = config.get("dcc_argv") or {}
    if isinstance(extra.get(dcc), list):
        argv.extend(extra[dcc])

    log.info("Spawning %s with ZENO_LAUNCH_CONTEXT intent=%s", exe, context.get("intent"))
    log.debug("Env ZENO_API_BASE_URL=%s", redact(api_base))

    # Detached process on POSIX; Windows: CREATE_NEW_PROCESS_GROUP
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]

    wd = config.get("working_directory")
    cwd = Path(wd).expanduser() if wd else Path.home()

    subprocess.Popen(
        argv,
        env=env,
        cwd=str(cwd),
        creationflags=creationflags if os.name == "nt" else 0,
        start_new_session=os.name != "nt",
    )
    return 0


def _inject_blender_bootstrap_if_needed(
    argv: list[str],
    env: dict[str, str],
    context: dict[str, Any],
    config: dict[str, Any],
) -> None:
    """
    For Blender launches, auto-enable/register chimera_zeno addon at startup so
    artists don't manually install/copy addon files in studio environments.
    """
    dcc = str(context.get("dcc") or "").lower()
    if dcc != "blender":
        return
    if config.get("blender_auto_bootstrap_addon", True) is False:
        return

    plugin_root = discover_zeno_plugin_root(config)
    if not plugin_root:
        return

    addon_root = Path(plugin_root) / "blender"
    if not (addon_root / "chimera_zeno").is_dir():
        return

    env["ZENO_PLUGIN_ROOT"] = plugin_root
    script = textwrap.dedent(
        f"""
        import importlib
        import os
        import subprocess
        import sys
        import traceback
        from pathlib import Path

        addon_root = {repr(str(addon_root))}
        plugin_root = {repr(str(plugin_root))}
        shared_deps = os.environ.get("ZENO_SHARED_DEPENDENCIES_PATH", "")
        module_name = "chimera_zeno"
        log_path = str(Path.home() / ".zeno_blender_bootstrap.log")

        def _log(msg):
            try:
                with open(log_path, "a", encoding="utf-8") as fh:
                    fh.write(msg + "\\n")
            except Exception:
                pass

        _log("bootstrap:start")
        _log(f"addon_root={{addon_root}}")
        _log(f"plugin_root={{plugin_root}}")
        if addon_root not in sys.path:
            sys.path.insert(0, addon_root)
        if plugin_root not in sys.path:
            sys.path.insert(0, plugin_root)
        if shared_deps:
            Path(shared_deps).mkdir(parents=True, exist_ok=True)
            if shared_deps not in sys.path:
                sys.path.insert(0, shared_deps)

        def _ensure_python_deps():
            required = ["blake3", "httpx"]
            missing = []
            for mod in required:
                try:
                    importlib.import_module(mod)
                except Exception:
                    missing.append(mod)
            if not missing:
                _log("deps:all-present")
                return
            _log(f"deps:missing={{missing}}")
            try:
                import ensurepip
                ensurepip.bootstrap()
            except Exception:
                _log("deps:ensurepip skipped/failed")
            try:
                py_bin = sys.executable
                candidate = Path(sys.prefix) / "bin" / f"python{{sys.version_info.major}}.{{sys.version_info.minor}}"
                if candidate.exists():
                    py_bin = str(candidate)
                _log(f"deps:python={{py_bin}}")
                # Install into shared bridge dependency directory (cross-DCC reuse).
                cmd = [py_bin, "-m", "pip", "install", "--target", shared_deps] + missing
                _log("deps:pip install " + " ".join(missing))
                subprocess.check_call(cmd)
                if shared_deps and shared_deps not in sys.path:
                    sys.path.insert(0, shared_deps)
                _log("deps:pip install ok")
            except Exception:
                _log("deps:pip install failed")
                _log(traceback.format_exc())

        _ensure_python_deps()

        try:
            import addon_utils
            enabled, loaded = addon_utils.check(module_name)
            _log(f"addon_utils:enabled={{enabled}} loaded={{loaded}}")
            if not enabled:
                addon_utils.enable(module_name, default_set=True, persistent=True)
                _log("addon_utils:enable called")
            enabled2, loaded2 = addon_utils.check(module_name)
            _log(f"addon_utils:after-enable enabled={{enabled2}} loaded={{loaded2}}")
            if (not enabled2) or (not loaded2):
                _log("addon not fully loaded; forcing manual import/register")
                mod = importlib.import_module(module_name)
                if hasattr(mod, "register"):
                    try:
                        mod.unregister()
                    except Exception:
                        pass
                    mod.register()
                    _log("manual register after addon_utils check: ok")
        except Exception:
            _log("addon_utils path failed; trying manual import/register")
            _log(traceback.format_exc())
            try:
                mod = importlib.import_module(module_name)
                if hasattr(mod, "register"):
                    try:
                        mod.unregister()
                    except Exception:
                        pass
                    mod.register()
                    _log("manual register ok")
            except Exception:
                _log("manual register failed")
                _log(traceback.format_exc())
        """
    )
    fd, script_path = tempfile.mkstemp(prefix="zeno_blender_bootstrap_", suffix=".py")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(script)

    argv.extend(["--python", script_path])


def _inject_pythonpath_for_dcc(env: dict[str, str], dcc: str, config: dict[str, Any]) -> None:
    extra = discover_python_paths_for_dcc(dcc, config)
    if not extra:
        return
    existing = env.get("PYTHONPATH", "").strip()
    parts = list(extra)
    if existing:
        parts.append(existing)
    env["PYTHONPATH"] = os.pathsep.join(parts)


def run_from_token(token: str, api_base: str | None = None) -> int:
    log = setup_logging()
    base = api_base or os.environ.get("ZENO_API_BASE_URL") or "http://127.0.0.1:8000"
    log.info("Exchanging launch token")
    data = exchange_token(base, token)
    ctx = data.get("context")
    if not isinstance(ctx, dict):
        log.error("Invalid exchange payload")
        return 1
    return spawn_dcc(ctx, api_base_override=base)

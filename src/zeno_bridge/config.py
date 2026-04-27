"""Load bridge config: DCC paths, API base URL, allowlist."""
from __future__ import annotations

import json
import os
import site
from pathlib import Path
from typing import Any


def default_config_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base / "ZenoBridge" / "config.json"
    return Path.home() / ".config" / "zeno-bridge" / "config.json"


def load_config(path: Path | None = None) -> dict[str, Any]:
    if path is not None:
        p = path
    elif os.environ.get("ZENO_BRIDGE_CONFIG"):
        p = Path(os.environ["ZENO_BRIDGE_CONFIG"])
    else:
        p = default_config_path()
    if not p.is_file():
        return {}
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def resolve_dcc_executable(dcc: str, config: dict[str, Any]) -> str | None:
    """Return absolute path to DCC binary if configured and allowlisted."""
    dccs = config.get("dcc_paths") or {}
    raw = dccs.get(dcc)
    if not raw:
        return None
    exe = Path(raw).expanduser().resolve()
    if not exe.is_file():
        return None
    allow = config.get("executable_allowlist") or []
    if allow:
        allowed = {Path(x).expanduser().resolve() for x in allow}
        if exe not in allowed:
            return None
    return str(exe)


def resolve_executable_from_launch_context(context: dict, config: dict[str, Any]) -> str | None:
    """
    Prefer API-resolved path from ZENO_LAUNCH_CONTEXT (dcc_executable_path) when present and valid.
    """
    raw = context.get("dcc_executable_path")
    if not raw or not isinstance(raw, str):
        return None
    exe = Path(raw).expanduser().resolve()
    if not exe.is_file():
        return None
    allow = config.get("executable_allowlist") or []
    if allow:
        allowed = {Path(x).expanduser().resolve() for x in allow}
        if exe not in allowed:
            return None
    return str(exe)


def discover_zeno_plugin_root(config: dict[str, Any]) -> str | None:
    """
    Locate zeno-plugin repo root for Blender bootstrap auto-registration.
    Priority:
    1) config['zeno_plugin_root']
    2) env ZENO_PLUGIN_ROOT
    3) sibling repo next to zeno-bridge in monorepo checkout
    """
    from_cfg = config.get("zeno_plugin_root")
    if isinstance(from_cfg, str) and from_cfg.strip():
        p = Path(from_cfg).expanduser().resolve()
        if (p / "blender" / "chimera_zeno").is_dir():
            return str(p)

    from_env = os.environ.get("ZENO_PLUGIN_ROOT", "").strip()
    if from_env:
        p = Path(from_env).expanduser().resolve()
        if (p / "blender" / "chimera_zeno").is_dir():
            return str(p)

    # zeno-bridge/src/zeno_bridge/config.py -> zeno-bridge ; sibling zeno-plugin
    bridge_repo = Path(__file__).resolve().parents[2]
    candidate = (bridge_repo.parent / "zeno-plugin").resolve()
    if (candidate / "blender" / "chimera_zeno").is_dir():
        return str(candidate)
    return None


def discover_python_paths_for_dcc(dcc: str, config: dict[str, Any]) -> list[str]:
    """
    Collect additional Python import paths to inject into DCC launches.
    Priority sources:
    1) config['pythonpath'] (global list)
    2) config['dcc_pythonpath'][dcc] (per-dcc list)
    3) env ZENO_BRIDGE_PYTHONPATH (os.pathsep-separated)
    4) current interpreter user site-packages and venv site-packages (if present)
    """
    out: list[str] = []

    def _append_paths(values: Any) -> None:
        if not isinstance(values, list):
            return
        for raw in values:
            if not isinstance(raw, str) or not raw.strip():
                continue
            p = Path(raw).expanduser().resolve()
            if p.exists():
                s = str(p)
                if s not in out:
                    out.append(s)

    _append_paths(config.get("pythonpath"))

    dcc_map = config.get("dcc_pythonpath")
    if isinstance(dcc_map, dict):
        _append_paths(dcc_map.get(dcc))

    env_raw = os.environ.get("ZENO_BRIDGE_PYTHONPATH", "")
    if env_raw.strip():
        for part in env_raw.split(os.pathsep):
            if not part.strip():
                continue
            p = Path(part).expanduser().resolve()
            if p.exists():
                s = str(p)
                if s not in out:
                    out.append(s)

    try:
        user_site = site.getusersitepackages()
        p = Path(user_site).expanduser().resolve()
        if p.exists():
            s = str(p)
            if s not in out:
                out.append(s)
    except Exception:
        pass

    venv = os.environ.get("VIRTUAL_ENV", "").strip()
    if venv:
        root = Path(venv).expanduser().resolve()
        pyver = f"python{os.sys.version_info.major}.{os.sys.version_info.minor}"
        for candidate in (
            root / "lib" / pyver / "site-packages",
            root / "Lib" / "site-packages",
        ):
            if candidate.exists():
                s = str(candidate)
                if s not in out:
                    out.append(s)

    return out


def discover_shared_dependencies_path(config: dict[str, Any]) -> str:
    """
    Shared dependency location used by bridge-launched DCCs.
    Priority:
    1) config['shared_dependencies_path']
    2) env ZENO_SHARED_DEPENDENCIES_PATH
    3) platform default under user home
    """
    raw = config.get("shared_dependencies_path")
    if isinstance(raw, str) and raw.strip():
        return str(Path(raw).expanduser().resolve())

    env_raw = os.environ.get("ZENO_SHARED_DEPENDENCIES_PATH", "").strip()
    if env_raw:
        return str(Path(env_raw).expanduser().resolve())

    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return str((base / "ZenoBridge" / "zeno-dependencies" / "py311").resolve())
    return str((Path.home() / ".local" / "share" / "zeno-bridge" / "zeno-dependencies" / "py311").resolve())

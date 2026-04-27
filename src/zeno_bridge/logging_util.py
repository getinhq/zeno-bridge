"""Redacted logging for bridge (no tokens in logs)."""
from __future__ import annotations

import logging
import os
import re
from pathlib import Path


_TOKENISH = re.compile(r"(token|secret|password|key)=[^&\s]+", re.I)


def setup_logging(log_path: Path | None = None) -> logging.Logger:
    log = logging.getLogger("zeno_bridge")
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG if os.environ.get("ZENO_BRIDGE_DEBUG") else logging.INFO)
    path = log_path or _default_log_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(path, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(fh)
    return log


def _default_log_path() -> Path:
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData/Local"))
        return base / "ZenoBridge" / "zeno-bridge.log"
    return Path.home() / ".local" / "share" / "zeno-bridge" / "zeno-bridge.log"


def redact(msg: str) -> str:
    return _TOKENISH.sub(r"\1=<redacted>", msg)

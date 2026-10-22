"""Open a review's original media in a local viewer (DJV, OpenRV...).

The dashboard sends the signed media path it got from the Zeno API. The bridge only ever
fetches it from its own configured API base (``config.resolve_api_base``) and only paths
under ``/api/v1/review-media/``, so a web page cannot make it download from elsewhere.
The viewer binary comes from local config (``viewers``) and must be in
``executable_allowlist``. Files are cached by content hash, so reopening is instant.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from zeno_bridge.config import resolve_api_base

MEDIA_PREFIX = "/api/v1/review-media/"
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")
_SAFE_NAME_RE = re.compile(r"[^A-Za-z0-9._-]+")


class MediaError(Exception):
    """Request rejected or could not be served; the message is shown to the user."""


def default_cache_dir() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "zeno-bridge" / "media"
    if os.name == "nt":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "zeno-bridge" / "media"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "zeno-bridge" / "media"


def resolve_viewer(name: str | None, config: dict[str, Any]) -> tuple[str, str]:
    """(viewer name, executable) from config['viewers'], allowlisted; first one by default."""
    viewers = config.get("viewers") or {}
    if not isinstance(viewers, dict) or not viewers:
        raise MediaError("No media viewer configured. Add \"viewers\": {\"djv\": \"/path/to/djv\"} to the bridge config.")
    key = name or next(iter(viewers))
    raw = viewers.get(key)
    if not raw:
        raise MediaError(f"Viewer '{key}' is not configured")
    exe = Path(str(raw)).expanduser().resolve()
    allowed = {Path(x).expanduser().resolve() for x in (config.get("executable_allowlist") or [])}
    if exe not in allowed:
        raise MediaError(f"Viewer '{key}' must be listed in executable_allowlist")
    if not exe.is_file():
        raise MediaError(f"Viewer '{key}' not found at {exe}")
    return key, str(exe)


def validate_media_path(path: str) -> str:
    """The signed path must be a relative review-media URL; returns its content id."""
    parsed = urlparse(path)
    if parsed.scheme or parsed.netloc or not parsed.path.startswith(MEDIA_PREFIX) or ".." in parsed.path:
        raise MediaError("Only Zeno review media can be opened")
    content_id = parsed.path[len(MEDIA_PREFIX):]
    if not _HASH_RE.match(content_id):
        raise MediaError("Only Zeno review media can be opened")
    return content_id


def safe_filename(name: str | None, content_id: str) -> str:
    base = Path(str(name or "")).name
    base = _SAFE_NAME_RE.sub("_", base).strip("._") or "media"
    return f"{content_id[:16]}_{base[:120]}"


def fetch_media(path: str, filename: str | None, config: dict[str, Any], cache_dir: Path | None = None) -> Path:
    content_id = validate_media_path(path)
    folder = cache_dir or Path(str(config.get("media_cache_dir") or "") or default_cache_dir())
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / safe_filename(filename, content_id)
    if target.is_file() and target.stat().st_size > 0:
        return target
    url = resolve_api_base(config) + path
    fd, tmp = tempfile.mkstemp(dir=folder, prefix=".download_")
    try:
        with os.fdopen(fd, "wb") as out, urllib.request.urlopen(url, timeout=60) as resp:  # noqa: S310 - fixed host
            while chunk := resp.read(1024 * 1024):
                out.write(chunk)
        os.replace(tmp, target)
    except Exception as exc:
        if os.path.exists(tmp):
            os.unlink(tmp)
        raise MediaError(f"Download failed: {exc}") from exc
    return target


def launch_viewer(exe: str, media: Path) -> None:
    kwargs: dict[str, Any] = {"stdin": subprocess.DEVNULL, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if os.name == "nt":
        kwargs["creationflags"] = getattr(subprocess, "DETACHED_PROCESS", 0)
    else:
        kwargs["start_new_session"] = True
    subprocess.Popen([exe, str(media)], **kwargs)  # noqa: S603 - allowlisted binary, no shell


def open_media(path: str, filename: str | None, viewer: str | None, config: dict[str, Any]) -> dict[str, str]:
    name, exe = resolve_viewer(viewer, config)
    media = fetch_media(path, filename, config)
    launch_viewer(exe, media)
    return {"viewer": name, "file": str(media)}

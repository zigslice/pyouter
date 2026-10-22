"""Static gd5-backed assets for the local web ui."""

from __future__ import annotations

import mimetypes
from pathlib import Path

ROOT = Path(__file__).resolve().parent

_CONTENT_TYPES = {
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".mjs": "text/javascript; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".map": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".woff": "font/woff",
    ".woff2": "font/woff2",
    ".txt": "text/plain; charset=utf-8",
}


def resolve_static(url_path: str):
    """Map ``/webui/...`` to a file under this package, or return None."""
    raw = "" if url_path is None else str(url_path)
    if raw.startswith("/webui/"):
        relative = raw[len("/webui/") :]
    elif raw.startswith("webui/"):
        relative = raw[len("webui/") :]
    else:
        return None
    if not relative or relative.endswith("/"):
        return None
    parts = relative.split("/")
    if any(part in ("", ".", "..") for part in parts):
        return None
    path = ROOT.joinpath(*parts).resolve()
    try:
        path.relative_to(ROOT)
    except ValueError:
        return None
    if not path.is_file():
        return None
    return path


def content_type_for(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in _CONTENT_TYPES:
        return _CONTENT_TYPES[suffix]
    guessed, _encoding = mimetypes.guess_type(str(path))
    return guessed or "application/octet-stream"


def read_static(url_path: str):
    """Return ``(bytes, content_type)`` for a webui URL, or None."""
    path = resolve_static(url_path)
    if path is None:
        return None
    return path.read_bytes(), content_type_for(path)

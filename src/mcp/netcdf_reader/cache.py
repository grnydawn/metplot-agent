"""⤴ format-agnostic — eligible for _core/ lift.

Inspection cache. Hash key includes path + mtime + size for local files
(the mtime is the invalidation signal); URL-only for remote (with
documented stale-data caveat). Cache lives in the per-project
.ncplot/inspections/ directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _cache_dir() -> Path:
    return Path.cwd() / ".ncplot" / "inspections"


def inspection_key(paths: list[str], *, remote: bool = False) -> str:
    h = hashlib.sha256()
    if remote:
        for p in sorted(paths):
            h.update(b"REMOTE\x00")
            h.update(p.encode("utf-8"))
            h.update(b"\x00")
    else:
        for p in sorted(paths):
            try:
                stat = Path(p).resolve().stat()
                h.update(p.encode("utf-8"))
                h.update(b"\x00")
                h.update(str(stat.st_mtime_ns).encode("ascii"))
                h.update(b"\x00")
                h.update(str(stat.st_size).encode("ascii"))
                h.update(b"\x00")
            except FileNotFoundError:
                h.update(p.encode("utf-8"))
                h.update(b"\x00MISSING\x00")
    return h.hexdigest()[:32]


def read_inspection(key: str) -> dict[str, Any] | None:
    fp = _cache_dir() / f"{key}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text())
    except json.JSONDecodeError:
        return None


def write_inspection(key: str, payload: dict[str, Any]) -> None:
    d = _cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(payload, indent=2))


class InspectionCache:
    """Thin convenience wrapper. Some tests want a class-style interface."""
    def __init__(self) -> None:
        self.dir = _cache_dir()

    def key(self, paths: list[str], *, remote: bool = False) -> str:
        return inspection_key(paths, remote=remote)

    def get(self, key: str) -> dict[str, Any] | None:
        return read_inspection(key)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        write_inspection(key, payload)

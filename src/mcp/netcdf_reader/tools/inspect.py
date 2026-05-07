# src/mcp/netcdf_reader/tools/inspect.py
"""⤴ format-agnostic — eligible for _core/ lift.

inspect() — full metadata summary of a file or multi-file dataset.
Cached at .ncplot/inspections/<hash>.json with mtime-based invalidation.
"""
from __future__ import annotations

from typing import Any

from src.mcp.netcdf_reader import cache, envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.conventions import cf as _cf
from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)


def inspect(path: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    try:
        cls = classify(path)
    except ClassifyError as e:
        # Distinguish "doesn't exist" from "unsupported scheme"
        msg = str(e)
        code = (envelope.ErrorCode.UNSUPPORTED_PATH_SCHEME
                if "unsupported scheme" in msg or "malformed" in msg
                else envelope.ErrorCode.FILE_NOT_FOUND)
        return envelope.error(code, msg, context={"path": path})

    is_remote = cls.kind in (PathKind.REMOTE_URL, PathKind.SSH_REMOTE)
    key = cache.inspection_key(cls.paths or [path], remote=is_remote)
    cached = cache.read_inspection(key)
    if cached is not None:
        return envelope.success(cached)

    try:
        ds = adapter.open(cls.paths)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"path": path})

    try:
        attrs = dict(ds.attrs)
        convention = adapter.detect_conventions(ds, attrs)
        result = {
            "path": cls.raw,
            "kind": cls.kind,
            "files": cls.paths,
            "convention": convention,
            "variables": _cf.extract_variables(ds),
            "time": _cf.extract_time(ds),
            "spatial": _cf.extract_spatial(ds),
            "vertical": _cf.extract_vertical(ds),
            "dims": {str(k): int(v) for k, v in ds.sizes.items()},
            "attrs": {k: _safe(v) for k, v in attrs.items()},
        }
    finally:
        ds.close()

    cache.write_inspection(key, result)
    return envelope.success(result)


def _safe(v: Any) -> Any:
    """Coerce attr value to JSON-safe scalar."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)

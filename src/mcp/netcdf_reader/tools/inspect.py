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
from src.mcp.netcdf_reader.conventions import roms as _roms
from src.mcp.netcdf_reader.conventions import wrf as _wrf
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
        ds = adapter.open(cls.paths or [path])
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"path": path})
    except OSError as e:
        # network or SSH-style errors
        msg = str(e)
        code = (envelope.ErrorCode.REMOTE_FILE_NOT_FOUND
                if cls.kind in ("remote_url", "ssh_remote")
                else envelope.ErrorCode.FILE_NOT_FOUND)
        return envelope.error(code, msg, context={"path": path})
    except Exception as e:
        return envelope.error(envelope.ErrorCode.INTERNAL_ERROR,
                              repr(e), context={"path": path})

    try:
        attrs = dict(ds.attrs)
        convention = adapter.detect_conventions(ds, attrs)
        primary = convention.get("primary")

        if primary == "WRF":
            variables = _wrf.annotate_staggered_variables(ds)
            spatial = _wrf.extract_spatial_wrf(ds)
            vertical = _cf.extract_vertical(ds)  # falls back; eta detected by name
            # WRF time decoding
            decoded = _wrf.decode_times(ds)
            t: dict[str, Any] | None
            if decoded is not None:
                t = {
                    "name": "Time",
                    "calendar": "standard",
                    "range": [str(decoded[0]), str(decoded[-1])],
                    "step": None,
                    "n": len(decoded),
                    "monotonic": "increasing",
                }
            else:
                t = _cf.extract_time(ds)
        elif primary == "ROMS":
            variables = _cf.extract_variables(ds)
            spatial = _roms.extract_spatial_roms(ds)
            vertical = _roms.extract_vertical_roms(ds)
            t = _cf.extract_time(ds)
        else:
            variables = _cf.extract_variables(ds)
            spatial = _cf.extract_spatial(ds)
            vertical = _cf.extract_vertical(ds)
            t = _cf.extract_time(ds)

        result = {
            "path": cls.raw,
            "kind": cls.kind,
            "files": cls.paths,
            "convention": convention,
            "variables": variables,
            "time": t,
            "spatial": spatial,
            "vertical": vertical,
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

"""⤴ format-agnostic — eligible for _core/ lift.

Output path resolution + auto-name + atomic save (Task 21).
Owns where figures land and how they get written (spec §5).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


_SUPPORTED_FORMATS = {"png", "pdf", "svg"}
_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")
_AUTO_DIR = ".ncplot/figures"


class OutputPathInvalid(ValueError):
    pass


class FormatExtensionMismatch(ValueError):
    pass


class UnsupportedFormat(ValueError):
    pass


def _ext_from_path(path: str) -> str | None:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or None


def _slug(s: str) -> str:
    s = _SLUG_RE.sub("-", s.strip().lower())
    return s.strip("-") or "plot"


def _spec_hash(spec: dict[str, Any]) -> str:
    """First 6 chars of sha256(canonical_json(spec))."""
    payload = json.dumps(spec, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:6]


def _when_token(spec: dict[str, Any]) -> str:
    """Best-effort first-time-coord token for auto-naming."""
    # render_map inline form
    coords = spec.get("coords") or {}
    times = coords.get("time") if isinstance(coords, dict) else None
    if not times:
        # render_timeseries: find earliest time across series
        series = spec.get("series")
        if isinstance(series, list) and series:
            ts = []
            for s in series:
                t = s.get("time")
                if isinstance(t, list) and t:
                    ts.append(t[0])
            if ts:
                first = min(ts)
                return str(first)[:7] if "T" not in str(first) \
                       else str(first)[:10]
        if isinstance(spec.get("time"), list) and spec["time"]:
            first = spec["time"][0]
            return str(first)[:10]
        if isinstance(series, list) and len(series) > 1:
            return "multi"
        return "unknown"
    if isinstance(times, list) and times:
        return str(times[0])[:10]
    return "unknown"


def resolve_output_path(
    output_path: str, fmt: str | None,
) -> str:
    """Validate explicit path and return absolute resolved path."""
    if not output_path:
        raise OutputPathInvalid("output_path must be a non-empty string")
    p = Path(output_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    ext = _ext_from_path(str(p))
    if ext is None:
        raise OutputPathInvalid("output_path has no file extension")
    if ext not in _SUPPORTED_FORMATS:
        raise UnsupportedFormat(
            f"unsupported format {ext!r}; supported: {sorted(_SUPPORTED_FORMATS)}")
    if fmt is not None and fmt != ext:
        raise FormatExtensionMismatch(
            f"format={fmt!r} disagrees with extension {ext!r}")
    return str(p)


def auto_name(*, tool: str, spec: dict[str, Any], fmt: str) -> str:
    """Build an auto-name path under .ncplot/figures/."""
    if fmt not in _SUPPORTED_FORMATS:
        raise UnsupportedFormat(
            f"unsupported format {fmt!r}; supported: {sorted(_SUPPORTED_FORMATS)}")
    var = spec.get("variable")
    title = spec.get("title")
    if isinstance(var, str) and var:
        var_or_label = _slug(var)
    elif isinstance(title, str) and title:
        var_or_label = _slug(title)
    else:
        var_or_label = "plot"
    when = _when_token(spec)
    h = _spec_hash(spec)
    name = f"{tool}_{var_or_label}_{when}_{h}.{fmt}"
    return str(Path.cwd() / _AUTO_DIR / name)

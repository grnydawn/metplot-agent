# src/mcp/netcdf_reader/tools/inspect.py
"""⤴ format-agnostic — eligible for _core/ lift.

inspect() — full metadata summary of a file or multi-file dataset.
Cached at .ncplot/inspections/<hash>.json with mtime-based invalidation.
"""
from __future__ import annotations

import time as _time
from typing import Any

from src.mcp.netcdf_reader import cache, envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.conventions import cf as _cf
from src.mcp.netcdf_reader.conventions import roms as _roms
from src.mcp.netcdf_reader.conventions import wrf as _wrf
from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)


def inspect(
    path: str, *,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    t0 = _time.monotonic()
    try:
        ds = adapter.open(cls.paths or [path], ssh_config=ssh_config)
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
        # Catch SSHAuthNeeded / SSHAuthFailed without importing at top
        # to keep paths/ssh.py optional for users who don't need SSH
        from src.mcp.netcdf_reader.paths.ssh import (
            SSHAuthNeeded, SSHAuthFailed,
        )
        if isinstance(e, SSHAuthNeeded):
            return _ssh_auth_needed_envelope(e)
        if isinstance(e, SSHAuthFailed):
            return _ssh_auth_failed_envelope(cls, str(e))
        return envelope.error(envelope.ErrorCode.INTERNAL_ERROR,
                              repr(e), context={"path": path})
    elapsed = _time.monotonic() - t0
    warnings: list[dict[str, Any]] = []
    if elapsed > 30 and cls.kind in (PathKind.REMOTE_URL, PathKind.SSH_REMOTE):
        warnings.append(envelope.warn(
            envelope.WarningCode.SLOW_REMOTE_READ,
            f"open took {elapsed:.0f}s; consider sshfs / staging",
            context={"elapsed_seconds": elapsed},
        ))

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
    return envelope.success(result, warnings=warnings)


def _safe(v: Any) -> Any:
    """Coerce attr value to JSON-safe scalar."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _ssh_auth_needed_envelope(err: "SSHAuthNeeded") -> dict[str, Any]:
    cfg = err.cfg
    candidates = [
        {"value": "identity_file", "label": "Path to a private key file",
         "param": "identity_file", "sensitive": False, "evidence": [],
         "confidence": 0.5},
        {"value": "password",
         "label": "Password (in-memory only, not stored)",
         "param": "password", "sensitive": True, "evidence": [],
         "confidence": 0.5},
        {"value": "ssh_config_alias",
         "label": "Use a ~/.ssh/config alias",
         "param": "ssh_alias", "sensitive": False, "evidence": [],
         "confidence": 0.5},
    ]
    tried = [
        {"method": a.method, "result": a.result, "detail": a.detail}
        for a in err.attempts
    ]
    return envelope.ambiguous(
        subcode=envelope.AmbiguitySubcode.SSH_AUTH_NEEDED,
        message=f"SSH authentication needed for {cfg.user}@{cfg.host}",
        candidates=candidates,
        prompt=(f"SSH auth needed for {cfg.user}@{cfg.host}. "
                f"Pick a method to authenticate."),
        retry_with_param="ssh_config",
        context={
            "host": cfg.host, "port": cfg.port, "user": cfg.user,
            "tried": tried, "may_need_jump_host": err.may_need_jump_host,
        },
    )


def _ssh_auth_failed_envelope(cls, msg: str) -> dict[str, Any]:
    # On wrong creds, route back to the prompt so the user can retry.
    candidates = [
        {"value": "password", "label": "Re-enter password",
         "param": "password", "sensitive": True, "evidence": [],
         "confidence": 0.5},
        {"value": "identity_file", "label": "Try a different key file",
         "param": "identity_file", "sensitive": False, "evidence": [],
         "confidence": 0.5},
    ]
    return envelope.ambiguous(
        subcode=envelope.AmbiguitySubcode.SSH_AUTH_NEEDED,
        message=f"SSH auth failed: {msg}",
        candidates=candidates,
        prompt=f"SSH auth was rejected. Pick a different method.",
        retry_with_param="ssh_config",
        context={"host": cls.host, "user": cls.user, "previous_error": msg},
    )

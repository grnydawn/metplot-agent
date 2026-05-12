# src/mcp/netcdf_reader/tools/inspect.py
"""⤴ format-agnostic — eligible for _core/ lift.

inspect() — full metadata summary of a file or multi-file dataset.
Cached at .metplot/inspections/<hash>.json with mtime-based invalidation.
"""
from __future__ import annotations

import time as _time
from typing import TYPE_CHECKING, Any

from src.mcp.netcdf_reader import cache, envelope
from src.mcp.netcdf_reader.conventions import cf as _cf
from src.mcp.netcdf_reader.conventions import mpas as _mpas
from src.mcp.netcdf_reader.conventions import roms as _roms
from src.mcp.netcdf_reader.conventions import wrf as _wrf
from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)
from src.mcp.netcdf_reader.paths.mesh_pair import find_mesh_candidates

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.paths.ssh import SSHAuthNeeded
    from src.mcp.netcdf_reader.protocols import FormatAdapter


def inspect(
    path: str, *,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
    mesh_path: str | None = None,
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

    cls_mesh = None
    if mesh_path is not None:
        try:
            cls_mesh = classify(mesh_path)
        except ClassifyError as e:
            msg = str(e)
            code = (envelope.ErrorCode.UNSUPPORTED_PATH_SCHEME
                    if "unsupported scheme" in msg or "malformed" in msg
                    else envelope.ErrorCode.FILE_NOT_FOUND)
            return envelope.error(code, msg,
                                  context={"path": mesh_path})

    is_remote = cls.kind in (PathKind.REMOTE_URL, PathKind.SSH_REMOTE)
    # Cycle 8 task 3: don't read/write the inspection cache when a
    # mesh_path is supplied. The cache key only encodes the primary
    # file list, so caching paired inspections would silently return
    # the unpaired envelope on retry. Bypassing keeps semantics
    # predictable; cycle-9 can extend the cache key if perf justifies.
    if mesh_path is None:
        key = cache.inspection_key(cls.paths or [path], remote=is_remote)
        cached = cache.read_inspection(key)
        if cached is not None:
            return envelope.success(cached)
    else:
        key = None

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

    # Open mesh-pair if supplied. Errors here close `ds` to avoid
    # leaking the opened history dataset's file handle.
    mesh_ds = None
    if cls_mesh is not None:
        # If cls_mesh is set, mesh_path was non-None on entry; this
        # assert narrows the Optional[str] for mypy and is a real
        # contract check.
        assert mesh_path is not None
        try:
            mesh_ds = adapter.open(cls_mesh.paths or [mesh_path],
                                    ssh_config=ssh_config)
        except FileNotFoundError as e:
            ds.close()
            return envelope.error(
                envelope.ErrorCode.FILE_NOT_FOUND,
                str(e), context={"mesh_path": mesh_path})
        except Exception as e:
            ds.close()
            return envelope.error(
                envelope.ErrorCode.INTERNAL_ERROR,
                f"failed to open mesh_path: {e!r}",
                context={"mesh_path": mesh_path})
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
        elif primary == "MPAS":
            variables = _cf.extract_variables(ds)
            vertical = _cf.extract_vertical(ds)
            t = _cf.extract_time(ds)
            if mesh_ds is not None:
                # Paired mode: validate dim-match, then extract
                # spatial from the mesh. Variables stay from the
                # history file; mesh geometry vars are kept out of
                # the variable listing (caller doesn't want
                # `verticesOnCell` in a plottable-variables list).
                from src.mcp.netcdf_reader.paths.mesh_pair import (
                    validate_mesh_pair,
                )
                err = validate_mesh_pair(ds, mesh_ds)
                if err:
                    return envelope.error(
                        envelope.ErrorCode.MULTI_FILE_COMBINE_FAILED,
                        f"history/mesh dim mismatch: {err}",
                        context={"path": path,
                                 "mesh_path": mesh_path})
                spatial = _mpas.extract_spatial_mpas(mesh_ds)
                # Tag history variables that share the cell dim with
                # the mesh — case-insensitive match per cycle-6
                # history-vs-mesh casing asymmetry.
                if spatial is not None:
                    cell_dim_lower = spatial["cell_dim"].lower()
                    for v in variables:
                        if any(str(d).lower() == cell_dim_lower
                                for d in v["dims"]):
                            v["grid_kind"] = "cell_centered"
            else:
                spatial = _mpas.extract_spatial_mpas(ds)
                if spatial is None and cls.kind == PathKind.LOCAL_SINGLE:
                    # MPAS file has the cell dim but no latCell/lonCell —
                    # the history-file-without-mesh shape. Short-circuit
                    # to a `mesh_pairing_required` ambiguous envelope so
                    # the caller can supply a mesh_path on retry.
                    # `ds.close()` fires in the outer finally block.
                    return _mesh_pairing_required_envelope(
                        path, variables)
        else:
            variables = _cf.extract_variables(ds)
            spatial = _cf.extract_spatial(ds)
            vertical = _cf.extract_vertical(ds)
            t = _cf.extract_time(ds)

        # If time extraction returned None but the file actually has a
        # Time-like dim, emit a structured warning so the user knows
        # the inspect tool noticed and chose not to fail. This is the
        # MPAS mesh-file shape (`Time` dim, no `time` variable) plus
        # any other file where time decode silently bailed.
        if t is None:
            for tname in ("time", "Time", "T", "ocean_time"):
                if tname in ds.dims and tname not in ds.variables:
                    warnings.append(envelope.warn(
                        envelope.WarningCode.TIME_DECODE_FAILED,
                        f"dim {tname!r} present but no decodable time "
                        f"coordinate; result.time = null",
                        context={"dim": tname,
                                 "size": int(ds.sizes[tname])},
                    ))
                    break

        files = list(cls.paths or [])
        if mesh_ds is not None and cls_mesh is not None:
            assert mesh_path is not None  # narrowed by cls_mesh check
            files.extend(cls_mesh.paths or [mesh_path])
        result = {
            "path": cls.raw,
            "kind": cls.kind,
            "files": files,
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
        if mesh_ds is not None:
            mesh_ds.close()

    if key is not None:
        cache.write_inspection(key, result)
    return envelope.success(result, warnings=warnings)


def _safe(v: Any) -> Any:
    """Coerce attr value to JSON-safe scalar."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)


def _mesh_pairing_required_envelope(
    path: str,
    variables: list[dict[str, Any]],
) -> dict[str, Any]:
    """Surface the history-file-without-mesh case as a structured
    ambiguous envelope so the caller can prompt the user for a
    mesh_path and retry. Cycle 8 §3.3.

    Candidates are derived from sibling-file naming heuristics in
    `paths/mesh_pair.find_mesh_candidates`. Confidence is "high" for
    the top match (exact-prefix or canonical name), "medium" for
    broader matches; for the cycle 8 MVP we don't try to dim-match
    here (that happens after retry, in the merged-pair load path)."""
    from pathlib import Path
    candidate_paths = find_mesh_candidates(Path(path))
    candidates = [
        {
            "value": str(p),
            "label": p.name,
            "param": "mesh_path",
            "sensitive": False,
            "evidence": [
                f"basename heuristic matched in {p.parent}",
            ],
            "confidence": 0.7 if i == 0 else 0.5,
        }
        for i, p in enumerate(candidate_paths)
    ]
    if candidates:
        prompt = (
            f"This MPAS history file ships no `latCell`/`lonCell` "
            f"coords. Likely sibling mesh files in the same "
            f"directory: {', '.join(p.name for p in candidate_paths)}. "
            f"Pick one (or supply a different path) and retry with "
            f"`mesh_path`.")
    else:
        prompt = (
            "This MPAS history file ships no `latCell`/`lonCell` "
            "coords. No likely sibling mesh files were found in the "
            "same directory; supply a `mesh_path` pointing at the "
            "matching MPAS mesh file and retry.")
    return envelope.ambiguous(
        subcode=envelope.AmbiguitySubcode.MESH_PAIRING_REQUIRED,
        message=(
            "MPAS history file requires a sibling mesh file to "
            "resolve spatial geometry"),
        candidates=candidates,
        prompt=prompt,
        retry_with_param="mesh_path",
        context={
            "path": path,
            "missing_coords": ["latCell", "lonCell"],
            "variables_in_history": [v["name"] for v in variables],
        },
    )


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
        prompt="SSH auth was rejected. Pick a different method.",
        retry_with_param="ssh_config",
        context={"host": cls.host, "user": cls.user, "previous_error": msg},
    )

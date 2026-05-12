# src/mcp/netcdf_reader/tools/read_slice.py
"""⤴ format-agnostic — eligible for _core/ lift.

read_slice() — hybrid output. Inline JSON for small slices; file path
for large slices (Task 16 adds the file-form branch).
"""
from __future__ import annotations

import hashlib
import json
import os
import time as _time
from pathlib import Path
from typing import TYPE_CHECKING, Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.paths.classify import classify
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.protocols import FormatAdapter

_SESSION_ID: str | None = None


def _session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = f"pid{os.getpid()}-{int(_time.time())}"
    return _SESSION_ID


def _slice_dir() -> Path:
    d = Path.cwd() / ".metplot" / "slices" / _session_id()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slice_hash(spec: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(json.dumps({
        "path": spec["path"],
        "variable": spec["variable"],
        "resolved": spec["resolved"],
        "applied_transforms": spec["applied_transforms"],
    }, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()[:16]


def _to_json_safe(arr: np.ndarray) -> Any:
    """Convert ndarray to nested list with NaN → 'NaN'."""
    out: list[Any] = []
    if arr.ndim == 0:
        v = arr.item()
        return "NaN" if isinstance(v, float) and np.isnan(v) else v
    for sub in arr:
        out.append(_to_json_safe(np.asarray(sub)))
    return out


def _apply_selectors(da, resolved: dict[str, Any]):
    """Apply resolved selectors to an xarray DataArray."""
    isel: dict[str, Any] = {}
    if "time_index" in resolved:
        for d in da.dims:
            if d in ("time", "Time", "ocean_time"):
                isel[d] = resolved["time_index"]
                break
    if "level_index" in resolved:
        # Case-insensitive set so MPAS dim casing
        # (NVertLayers history vs nVertLevels mesh) just works.
        _lev_dims = {"plev", "lev", "level", "bottom_top",
                     "nvertlayers", "nvertlevels"}
        for d in da.dims:
            if str(d).lower() in _lev_dims:
                isel[d] = resolved["level_index"]
                break
    if "lat_indices" in resolved:
        for d in da.dims:
            if d in ("lat", "latitude", "y"):
                lo, hi = resolved["lat_indices"]
                isel[d] = slice(lo, hi + 1)
                break
    if "lat_index" in resolved:
        for d in da.dims:
            if d in ("lat", "latitude", "y"):
                isel[d] = resolved["lat_index"]
                break
    if "lon_indices" in resolved:
        for d in da.dims:
            if d in ("lon", "longitude", "x"):
                lo, hi = resolved["lon_indices"]
                isel[d] = slice(lo, hi + 1)
                break
    if "lon_index" in resolved:
        for d in da.dims:
            if d in ("lon", "longitude", "x"):
                isel[d] = resolved["lon_index"]
                break
    return da.isel(**isel)


def read_slice(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    regrid: str | None = None,
    max_inline_bytes: int = 100_000,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
    mesh_path: str | None = None,
) -> dict[str, Any]:
    spec_env = resolve_spec(
        path, variable, time=time, level=level, lat=lat, lon=lon,
        region=region, regrid=regrid, adapter=adapter,
        ssh_config=ssh_config, mesh_path=mesh_path,
    )
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]
    estimated = int(spec["estimated_bytes"])

    if estimated > max_inline_bytes:
        cls = classify(path)
        ds = adapter.open(cls.paths, ssh_config=ssh_config)
        try:
            da = _apply_selectors(ds[variable], spec["resolved"])
            sliced = da.load()
            out_path = _slice_dir() / f"{_slice_hash(spec)}.nc"
            sliced.to_netcdf(out_path)
            values = sliced.values
            nan_count = int(np.isnan(values).sum()) if values.dtype.kind == "f" else 0
            total = int(values.size)
            stats = {
                "min": float(np.nanmin(values)) if values.dtype.kind == "f" else float(values.min()),
                "max": float(np.nanmax(values)) if values.dtype.kind == "f" else float(values.max()),
                "mean": float(np.nanmean(values)) if values.dtype.kind == "f" else float(values.mean()),
                "fraction_nan": nan_count / total if total else 0.0,
            }
            coords_summary: dict[str, dict[str, Any]] = {}
            for d in sliced.dims:
                if d in sliced.coords:
                    cv = np.asarray(sliced[d].values)
                    coords_summary[str(d)] = {
                        "n": int(cv.size),
                        "range": [_to_json_safe(cv.min()), _to_json_safe(cv.max())],
                    }
            result = {
                "form": "file",
                "path": str(out_path),
                "format": "netcdf",
                "size_bytes": out_path.stat().st_size,
                "dims": [str(d) for d in sliced.dims],
                "shape": list(values.shape),
                "coords_summary": coords_summary,
                "units": ds[variable].attrs.get("units"),
                "stats": stats,
            }
            if mesh_path is not None:
                result["mesh_path"] = mesh_path
            return envelope.success(result)
        finally:
            ds.close()

    cls = classify(path)
    ds = adapter.open(cls.paths, ssh_config=ssh_config)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        nan_count = int(np.isnan(values).sum()) if values.dtype.kind == "f" else 0
        total = int(values.size)
        stats = {
            "min": float(np.nanmin(values)) if values.dtype.kind == "f" else float(values.min()),
            "max": float(np.nanmax(values)) if values.dtype.kind == "f" else float(values.max()),
            "mean": float(np.nanmean(values)) if values.dtype.kind == "f" else float(values.mean()),
            "fraction_nan": nan_count / total if total else 0.0,
        }
        coords_out: dict[str, list[Any]] = {}
        for d in da.dims:
            if d in da.coords:
                coords_out[str(d)] = _to_json_safe(np.asarray(da[d].values))
        result = {
            "form": "inline",
            "values": _to_json_safe(values),
            "coords": coords_out,
            "dims": [str(d) for d in da.dims],
            "shape": list(values.shape),
            "units": ds[variable].attrs.get("units"),
            "stats": stats,
        }
        if mesh_path is not None:
            result["mesh_path"] = mesh_path
        return envelope.success(result)
    finally:
        ds.close()

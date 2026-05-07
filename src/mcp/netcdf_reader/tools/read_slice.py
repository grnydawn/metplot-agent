# src/mcp/netcdf_reader/tools/read_slice.py
"""⤴ format-agnostic — eligible for _core/ lift.

read_slice() — hybrid output. Inline JSON for small slices; file path
for large slices (Task 16 adds the file-form branch).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


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
    sel: dict[str, Any] = {}
    isel: dict[str, Any] = {}
    if "time_index" in resolved:
        for d in da.dims:
            if d in ("time", "Time", "ocean_time"):
                isel[d] = resolved["time_index"]
                break
    if "level_index" in resolved:
        for d in da.dims:
            if d in ("plev", "lev", "level", "bottom_top"):
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
) -> dict[str, Any]:
    spec_env = resolve_spec(
        path, variable, time=time, level=level, lat=lat, lon=lon,
        region=region, regrid=regrid, adapter=adapter,
    )
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]
    estimated = int(spec["estimated_bytes"])

    if estimated > max_inline_bytes:
        # File-form lands in Task 16. Until then, return size_limit_exceeded.
        return envelope.error(
            envelope.ErrorCode.SIZE_LIMIT_EXCEEDED,
            f"slice would be {estimated} bytes, exceeds {max_inline_bytes}",
            context={"estimated_bytes": estimated,
                     "max_inline_bytes": max_inline_bytes,
                     "shape": spec["slice_shape"]},
        )

    cls = classify(path)
    ds = adapter.open(cls.paths)
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
        return envelope.success(result)
    finally:
        ds.close()

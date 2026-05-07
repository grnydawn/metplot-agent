"""⤴ format-agnostic — eligible for _core/ lift.

peek() — single-point or tiny-area value lookup. Hard-capped at
PEEK_HARD_CAP_BYTES. Refuses larger requests with size_limit_exceeded.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.paths.classify import classify
from src.mcp.netcdf_reader.tools.read_slice import _apply_selectors, _to_json_safe
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec

if TYPE_CHECKING:
    from src.mcp.netcdf_reader.protocols import FormatAdapter

PEEK_HARD_CAP_BYTES = 10_000


def peek(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec_env = resolve_spec(path, variable, time=time, level=level,
                             lat=lat, lon=lon, adapter=adapter,
                             ssh_config=ssh_config)
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]
    if spec["estimated_bytes"] > PEEK_HARD_CAP_BYTES:
        return envelope.error(
            envelope.ErrorCode.SIZE_LIMIT_EXCEEDED,
            f"peek refuses {spec['estimated_bytes']}-byte slice (cap {PEEK_HARD_CAP_BYTES})",
            context={"estimated_bytes": spec["estimated_bytes"],
                     "cap": PEEK_HARD_CAP_BYTES,
                     "shape": spec["slice_shape"]},
        )

    cls = classify(path)
    ds = adapter.open(cls.paths, ssh_config=ssh_config)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        coords_out: dict[str, Any] = {}
        dist: dict[str, Any] = {}
        for d in da.dims:
            if d in da.coords:
                cv = np.asarray(da[d].values)
                if cv.ndim == 0:
                    coords_out[str(d)] = _to_json_safe(cv)
                else:
                    coords_out[str(d)] = _to_json_safe(cv)
        # Distance-to-nearest only meaningful for point selectors
        if isinstance(lat, (int, float)) and "lat_index" in spec["resolved"]:
            actual = float(ds[next(d for d in ds[variable].dims
                                   if d in ("lat", "latitude", "y"))]
                           .values[spec["resolved"]["lat_index"]])
            dist["lat_deg"] = abs(actual - float(lat))
        if isinstance(lon, (int, float)) and "lon_index" in spec["resolved"]:
            actual = float(ds[next(d for d in ds[variable].dims
                                   if d in ("lon", "longitude", "x"))]
                           .values[spec["resolved"]["lon_index"]])
            dist["lon_deg"] = abs(actual - float(lon))

        result = {
            "value": _to_json_safe(values),
            "shape": list(values.shape),
            "coords": coords_out,
            "units": ds[variable].attrs.get("units"),
            "distance_to_nearest": dist,
        }
        return envelope.success(result)
    finally:
        ds.close()

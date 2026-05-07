# src/mcp/netcdf_reader/tools/compute_stats.py
"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import classify
from src.mcp.netcdf_reader.tools.read_slice import _apply_selectors
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def compute_stats(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    spec_env = resolve_spec(
        path, variable, time=time, level=level, lat=lat, lon=lon,
        region=region, adapter=adapter,
        ssh_config=ssh_config,
    )
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]

    cls = classify(path)
    ds = adapter.open(cls.paths, ssh_config=ssh_config)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        is_float = values.dtype.kind == "f"
        nan_count = int(np.isnan(values).sum()) if is_float else 0
        total = int(values.size)
        if is_float:
            arr_clean = values[~np.isnan(values)]
        else:
            arr_clean = values
        if arr_clean.size == 0:
            return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                  "no non-NaN values", context={})
        result = {
            "min": float(arr_clean.min()),
            "max": float(arr_clean.max()),
            "mean": float(arr_clean.mean()),
            "std": float(arr_clean.std()),
            "count": total,
            "fraction_nan": nan_count / total if total else 0.0,
            "percentiles": {
                "p5": float(np.percentile(arr_clean, 5)),
                "p50": float(np.percentile(arr_clean, 50)),
                "p95": float(np.percentile(arr_clean, 95)),
            },
            "units": ds[variable].attrs.get("units"),
            "shape_summarized": list(values.shape),
        }
        return envelope.success(result)
    finally:
        ds.close()

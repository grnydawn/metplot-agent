"""Format-specific (NetCDF): ROMS-aware detection and helpers."""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []
    if any(d in ds.dims for d in ("s_rho", "s_w")):
        evidence.append("ROMS sigma dim present (s_rho/s_w)")
    if "Cs_r" in ds.data_vars or "Cs_w" in ds.data_vars:
        evidence.append("Cs_r/Cs_w stretching variable present")
    if any(name in ds.data_vars or name in ds.coords
           for name in ("lat_rho", "lon_rho", "lat_u", "lon_u")):
        evidence.append("ROMS lat/lon_rho coords present")
    title = attrs.get("type", "")
    if isinstance(title, str) and "ROMS" in title.upper():
        evidence.append(f"type attr = {title!r}")

    if not evidence:
        return None
    confidence = "high" if len(evidence) >= 2 else "medium"
    return {
        "primary": "ROMS",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def extract_spatial_roms(ds: xr.Dataset) -> dict[str, Any] | None:
    if "lat_rho" not in ds.data_vars and "lat_rho" not in ds.coords:
        return None
    lat = ds["lat_rho"]; lon = ds["lon_rho"]
    coord_kind = "curvilinear" if lat.ndim == 2 else "rectilinear"
    lon_min = float(lon.min()); lon_max = float(lon.max())
    if lon_min >= 0 and lon_max > 180:
        conv = "0..360"
    elif lon_min < 0:
        conv = "-180..180"
    else:
        conv = "mixed"
    return {
        "coord_kind": coord_kind,
        "lat_name": "lat_rho",
        "lon_name": "lon_rho",
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": conv,
    }


def extract_vertical_roms(ds: xr.Dataset) -> dict[str, Any] | None:
    name = "s_rho" if "s_rho" in ds.dims else ("s_w" if "s_w" in ds.dims else None)
    if name is None:
        return None
    n = int(ds.sizes[name])
    coord = ds[name] if name in ds.coords else None
    monotonic = "unknown"
    if coord is not None and n > 1:
        diffs = np.diff(coord.values)
        if np.all(diffs > 0):
            monotonic = "increasing"
        elif np.all(diffs < 0):
            monotonic = "decreasing"
    return {
        "name": name,
        "kind": "sigma",
        "units": coord.attrs.get("units") if coord is not None else None,
        "n": n,
        "monotonic": monotonic,
    }

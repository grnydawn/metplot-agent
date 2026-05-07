# src/mcp/netcdf_reader/conventions/cf.py
"""⤴ format-agnostic — eligible for _core/ lift.

CF (and CF-derived: CMIP) detection. WRF/ROMS detection lives in
conventions/wrf.py and conventions/roms.py respectively. This module
detects CF-family conventions and extracts CF-defined metadata
(time, spatial, vertical coords).
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
    evidence: list[str] = []
    primary = "unknown"
    confidence = "low"

    conv = attrs.get("Conventions", "")
    if isinstance(conv, str) and conv.upper().startswith("CF"):
        primary = "CF"
        confidence = "high"
        evidence.append(f"Conventions attr = {conv!r}")

    if "mip_era" in attrs or "cmor_version" in attrs:
        # CMIP files always have Conventions=CF-1.x AND mip_era / cmor_version
        primary = "CMIP"
        confidence = "high"
        if "mip_era" in attrs:
            evidence.append(f"mip_era attr = {attrs['mip_era']!r}")
        if "cmor_version" in attrs:
            evidence.append(f"cmor_version attr = {attrs['cmor_version']!r}")

    candidates = None
    if primary == "unknown":
        # Soft signals: presence of standard_name on at least one variable
        soft_evidence = []
        for vname, var in ds.data_vars.items():
            if "standard_name" in var.attrs:
                soft_evidence.append(f"{vname} has standard_name attr")
                break
        if soft_evidence:
            primary = "CF"
            confidence = "low"
            evidence.extend(soft_evidence)
            candidates = [
                {"convention": "CF", "confidence": 0.5, "evidence": soft_evidence},
                {"convention": "unknown", "confidence": 0.5, "evidence": []},
            ]
        else:
            # No conventions attr and no soft signals — record uncertainty.
            candidates = [
                {"convention": "unknown", "confidence": 1.0, "evidence": []},
            ]

    return {
        "primary": primary,
        "confidence": confidence,
        "evidence": evidence,
        "candidates": candidates,
    }


_LAT_NAMES = ("lat", "latitude", "y", "rlat", "nav_lat")
_LON_NAMES = ("lon", "longitude", "x", "rlon", "nav_lon")
_TIME_NAMES = ("time", "Time", "T", "ocean_time")


def extract_variables(ds: xr.Dataset) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, da in ds.data_vars.items():
        is_stag = any("stag" in str(d).lower() for d in da.dims)
        out.append({
            "name": str(name),
            "long_name": da.attrs.get("long_name"),
            "standard_name": da.attrs.get("standard_name"),
            "description": da.attrs.get("description"),
            "units": da.attrs.get("units"),
            "dims": [str(d) for d in da.dims],
            "shape": list(da.shape),
            "dtype": str(da.dtype),
            "grid_kind": "scalar",
            "is_staggered": is_stag,
        })
    return out


def _find_coord(ds: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    for n in candidates:
        if n in ds.coords or n in ds.dims:
            return n
    return None


def extract_time(ds: xr.Dataset) -> dict[str, Any] | None:
    name = _find_coord(ds, _TIME_NAMES)
    if name is None:
        return None
    coord = ds[name]
    values = coord.values
    n = len(values)
    if n == 0:
        return {"name": name, "n": 0, "calendar": "unknown",
                "range": [], "step": None, "monotonic": "unknown"}
    diffs = np.diff(values) if n > 1 else None
    if diffs is None or len(diffs) == 0:
        monotonic = "unknown"
    elif np.all(diffs > np.timedelta64(0, "ns")):
        monotonic = "increasing"
    elif np.all(diffs < np.timedelta64(0, "ns")):
        monotonic = "decreasing"
    else:
        monotonic = "non-monotonic"
    # Calendar — xarray sets it on the coord's encoding or attrs
    calendar = coord.encoding.get("calendar") or coord.attrs.get("calendar") or "standard"
    # Step (uniform diff if all equal)
    step = None
    if diffs is not None and len(diffs) > 0:
        if np.all(diffs == diffs[0]):
            step = _timedelta_to_iso(diffs[0])
    return {
        "name": name,
        "n": n,
        "calendar": str(calendar),
        "range": [_dt_to_iso(values[0]), _dt_to_iso(values[-1])],
        "step": step,
        "monotonic": monotonic,
    }


def _dt_to_iso(v: Any) -> str:
    return np.datetime_as_string(v, unit="s") if hasattr(v, "astype") else str(v)


def _timedelta_to_iso(td: np.timedelta64) -> str:
    seconds = int(td / np.timedelta64(1, "s"))
    if seconds % 86400 == 0:
        return f"P{seconds // 86400}D"
    if seconds % 3600 == 0:
        return f"PT{seconds // 3600}H"
    if seconds % 60 == 0:
        return f"PT{seconds // 60}M"
    return f"PT{seconds}S"


def extract_spatial(ds: xr.Dataset) -> dict[str, Any] | None:
    lat_name = _find_coord(ds, _LAT_NAMES)
    lon_name = _find_coord(ds, _LON_NAMES)
    if lat_name is None or lon_name is None:
        return None
    lat = ds[lat_name]
    lon = ds[lon_name]
    coord_kind = "rectilinear" if lat.ndim == 1 and lon.ndim == 1 else "curvilinear"
    lon_min = float(lon.min())
    lon_max = float(lon.max())
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"
    return {
        "coord_kind": coord_kind,
        "lat_name": lat_name,
        "lon_name": lon_name,
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": lon_convention,
    }


_VERTICAL_KINDS = {
    "plev": "pressure", "lev": "model_level", "level": "model_level",
    "altitude": "height", "z": "height",
    "bottom_top": "eta", "bottom_top_stag": "eta",
    "s_rho": "sigma", "s_w": "sigma",
}


def extract_vertical(ds: xr.Dataset) -> dict[str, Any] | None:
    for cand_name, kind in _VERTICAL_KINDS.items():
        if cand_name in ds.coords or cand_name in ds.dims:
            coord = ds[cand_name] if cand_name in ds.coords else None
            n = ds.sizes[cand_name]
            if coord is None or n == 0:
                return {"name": cand_name, "kind": kind, "units": None,
                        "n": n, "monotonic": "unknown"}
            values = coord.values
            diffs = np.diff(values) if n > 1 else None
            if diffs is None or len(diffs) == 0:
                monotonic = "unknown"
            elif np.all(diffs > 0):
                monotonic = "increasing"
            elif np.all(diffs < 0):
                monotonic = "decreasing"
            else:
                monotonic = "non-monotonic"
            return {
                "name": cand_name,
                "kind": kind,
                "units": coord.attrs.get("units"),
                "n": int(n),
                "monotonic": monotonic,
            }
    return None

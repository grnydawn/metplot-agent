# src/mcp/netcdf_reader/conventions/wrf.py
"""Format-specific (NetCDF): WRF-aware detection and helpers.
WRF is not CF-compliant; we surface it at inspect time so skills
and consumers can apply WRF-aware logic.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions import cf as _cf


_STAGGERED_DIMS = {"west_east_stag", "south_north_stag", "bottom_top_stag"}


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []

    title = attrs.get("TITLE", "")
    if isinstance(title, str) and "WRF" in title.upper():
        evidence.append(f"TITLE attr matches {title!r}")
    if "MMINLU" in attrs:
        evidence.append(f"MMINLU attr present (value={attrs['MMINLU']!r})")

    staggered = _STAGGERED_DIMS & set(map(str, ds.dims))
    if staggered:
        evidence.append(f"WRF-style staggered dims present: {sorted(staggered)}")

    if "Times" in ds.data_vars and ds["Times"].dtype.kind in ("S", "O"):
        evidence.append("Times byte-string variable present")

    if not evidence:
        return None

    if any("TITLE" in e for e in evidence):
        confidence = "high"
    elif len(evidence) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "primary": "WRF",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def decode_times(ds: xr.Dataset) -> np.ndarray | None:
    """Decode WRF Times byte-string array to CF datetime64."""
    if "Times" not in ds.data_vars:
        return None
    raw = ds["Times"].values
    # raw is shape (n_time, str_len) of bytes. Stitch bytes per row.
    if raw.ndim == 2:
        rows = [b"".join(row).decode("ascii", errors="replace") for row in raw]
    else:
        rows = [s.decode("ascii", errors="replace") if isinstance(s, bytes) else str(s)
                for s in raw]
    # WRF format: "2024-09-01_06:00:00" → ISO "2024-09-01T06:00:00"
    iso = [s.replace("_", "T").rstrip("\x00 ") for s in rows]
    return np.array(iso, dtype="datetime64[s]")


def _grid_kind_from_dims(dims: tuple[str, ...]) -> str:
    if "west_east_stag" in dims:
        return "U"
    if "south_north_stag" in dims:
        return "V"
    if "bottom_top_stag" in dims:
        return "W"
    return "scalar"


def annotate_staggered_variables(ds: xr.Dataset) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, da in ds.data_vars.items():
        gk = _grid_kind_from_dims(tuple(str(d) for d in da.dims))
        out.append({
            "name": str(name),
            "long_name": _cf.normalize_name_attr(
                da.attrs.get("long_name") or da.attrs.get("description")),
            "standard_name": _cf.normalize_name_attr(
                da.attrs.get("standard_name")),
            "units": da.attrs.get("units"),
            "dims": [str(d) for d in da.dims],
            "shape": list(da.shape),
            "dtype": str(da.dtype),
            "grid_kind": gk,
            "is_staggered": gk != "scalar",
        })
    return out


def extract_spatial_wrf(ds: xr.Dataset) -> dict[str, Any] | None:
    if "XLAT" not in ds.coords and "XLAT" not in ds.data_vars:
        return None
    lat = ds["XLAT"]
    lon = ds["XLONG"]
    # WRF XLAT/XLONG can be (Time, south_north, west_east); take first time
    if lat.ndim == 3:
        lat = lat.isel({lat.dims[0]: 0})
        lon = lon.isel({lon.dims[0]: 0})
    coord_kind = "curvilinear" if lat.ndim == 2 else "rectilinear"
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
        "lat_name": "XLAT",
        "lon_name": "XLONG",
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": lon_convention,
    }

"""Cycle 11 — selector helpers for unstructured-mesh time-series /
profile workflows.  Cycle 13 generalized off MPAS-only.

Three helpers feed the skill-side spatial reduction:

  find_nearest_cell(mesh_ds, lat, lon, convention="auto") -> int
    Great-circle (haversine) distance from (lat, lon) to every
    cell center. Returns the int index of the nearest.

  cells_in_bbox(mesh_ds, lat_min, lat_max, lon_min, lon_max,
                convention="auto")            -> np.ndarray[int]
    Cell indices whose center falls in the bbox. Handles
    cross-dateline (lon_min > lon_max).

  area_weights(mesh_ds, indices=None, convention="auto")
                                                 -> np.ndarray
    Returns 1-D weights array. Uses the family's area variable
    if present; uniform fallback otherwise.

`convention` defaults to `"auto"` and is sniffed from the mesh's
variable names: MPAS uses `latCell/lonCell/areaCell` on
`nCells`; CICE uses `TLAT/TLON/tarea` on `ni`; EAMxx uses
`lat/lon/area` on `ncol`. Explicit conventions
(`"MPAS" | "CICE" | "EAMxx"`) force the choice.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.mpas import _to_degrees_if_radians

_EARTH_RADIUS_KM = 6371.0


# Per-family mesh-variable triples: (lat_var, lon_var, area_var, cell_dim).
_FAMILIES: dict[str, tuple[str, str, str, str]] = {
    "MPAS":  ("latCell", "lonCell", "areaCell", "nCells"),
    "CICE":  ("TLAT",    "TLON",    "tarea",    "ni"),
    "EAMxx": ("lat",     "lon",     "area",     "ncol"),
}


def _detect_convention(mesh_ds: xr.Dataset) -> str:
    """Sniff which family this mesh belongs to from its variables.
    Order matters: MPAS first (most specific names), then CICE,
    then EAMxx (most generic names — `lat`/`lon` collide with
    rectilinear coords)."""
    for name, (lat_v, lon_v, _, cell_dim) in _FAMILIES.items():
        if (lat_v in mesh_ds.variables
                and lon_v in mesh_ds.variables
                and cell_dim in mesh_ds.sizes):
            return name
    raise ValueError(
        "could not detect mesh convention; expected one of MPAS "
        "(latCell/lonCell/nCells), CICE (TLAT/TLON/ni), or EAMxx "
        f"(lat/lon/ncol). Mesh has variables: "
        f"{sorted(mesh_ds.variables)[:10]}")


def _resolve_mesh_vars(mesh_ds: xr.Dataset, convention: str = "auto"
                        ) -> tuple[str, str, str, str]:
    """Return (lat_var, lon_var, area_var, cell_dim) for this mesh."""
    if convention == "auto":
        convention = _detect_convention(mesh_ds)
    if convention not in _FAMILIES:
        raise ValueError(
            f"unknown convention {convention!r}; expected one of "
            f"{list(_FAMILIES.keys()) + ['auto']}")
    return _FAMILIES[convention]


def _coords_deg(mesh_ds: xr.Dataset, convention: str = "auto"
                 ) -> tuple[np.ndarray, np.ndarray]:
    """Pull lat / lon as 1-D degree arrays, applying the cycle-9
    radian-detection heuristic. Family-aware (cycle 13)."""
    lat_v, lon_v, _, _ = _resolve_mesh_vars(mesh_ds, convention)
    lat = _to_degrees_if_radians(
        np.asarray(mesh_ds[lat_v].values, dtype=float),
        mesh_ds[lat_v].attrs)
    lon = _to_degrees_if_radians(
        np.asarray(mesh_ds[lon_v].values, dtype=float),
        mesh_ds[lon_v].attrs)
    return lat, lon


def find_nearest_cell(mesh_ds: xr.Dataset, *,
                       lat: float, lon: float,
                       convention: str = "auto") -> int:
    """Return the integer cell index whose great-circle distance to
    (lat, lon) is minimal. (lat, lon) are in degrees. Family-aware
    via `convention` (cycle 13)."""
    lats, lons = _coords_deg(mesh_ds, convention)
    lat_r = np.radians(lats)
    lon_r = np.radians(lons)
    tgt_lat_r = np.radians(lat)
    tgt_lon_r = np.radians(lon)
    # Haversine — angular distance only (R is constant; argmin same).
    dlat = lat_r - tgt_lat_r
    dlon = lon_r - tgt_lon_r
    a = (np.sin(dlat / 2) ** 2
         + np.cos(tgt_lat_r) * np.cos(lat_r) * np.sin(dlon / 2) ** 2)
    # Clip to avoid arcsin domain errors from tiny floating overshoot.
    a = np.clip(a, 0.0, 1.0)
    d_ang = 2 * np.arcsin(np.sqrt(a))
    return int(np.argmin(d_ang))


def cells_in_bbox(mesh_ds: xr.Dataset, *,
                    lat_min: float, lat_max: float,
                    lon_min: float, lon_max: float,
                    convention: str = "auto") -> np.ndarray:
    """Return cell indices whose center falls in the bbox.
    Cross-dateline bboxes (lon_min > lon_max) wrap. Family-aware
    via `convention` (cycle 13).

    Lon convention agnostic: callers can supply either 0..360 or
    -180..180. The bbox compares against the mesh's lon coords as
    they are (after the radian-to-degree conversion); cross-
    dateline detection is purely numeric (lon_min > lon_max).
    """
    lats, lons = _coords_deg(mesh_ds, convention)
    lat_ok = (lats >= lat_min) & (lats <= lat_max)
    if lon_min <= lon_max:
        lon_ok = (lons >= lon_min) & (lons <= lon_max)
    else:
        # Cross-dateline: union of [lon_min, +inf) and (-inf, lon_max].
        lon_ok = (lons >= lon_min) | (lons <= lon_max)
    return np.where(lat_ok & lon_ok)[0].astype(np.int64)


def area_weights(mesh_ds: xr.Dataset, *,
                  indices: np.ndarray | None = None,
                  convention: str = "auto") -> np.ndarray:
    """Return per-cell weights. Uses the family's area variable
    when present; uniform fallback otherwise. Subset to `indices`
    when supplied. Family-aware (cycle 13).

    Callers normalize as needed (weights.sum() may be != 1).
    """
    _, _, area_v, cell_dim = _resolve_mesh_vars(mesh_ds, convention)
    if area_v in mesh_ds.variables:
        w = np.asarray(mesh_ds[area_v].values, dtype=float)
    else:
        n = int(mesh_ds.sizes[cell_dim])
        w = np.ones(n, dtype=float)
    if indices is not None:
        w = w[np.asarray(indices)]
    return w


# ── MCP-facing entry points ────────────────────────────────────
#
# These wrappers open the mesh file, call the underlying helper, and
# wrap the result in the standard envelope. They're what server.py
# dispatches to so skills can invoke the helpers via the MCP boundary
# the same way they invoke find_variables / find_time.

def _open_mesh(mesh_path: str, *, adapter: Any
                ) -> tuple[xr.Dataset | None, dict[str, Any] | None]:
    """Shared open-with-error-handling for the MCP wrappers."""
    from src.mcp.netcdf_reader import envelope
    from src.mcp.netcdf_reader.paths.classify import (
        ClassifyError, classify,
    )
    try:
        cls = classify(mesh_path)
    except ClassifyError as e:
        return None, envelope.error(
            envelope.ErrorCode.FILE_NOT_FOUND, str(e),
            context={"mesh_path": mesh_path})
    try:
        return adapter.open(cls.paths or [mesh_path]), None
    except FileNotFoundError as e:
        return None, envelope.error(
            envelope.ErrorCode.FILE_NOT_FOUND, str(e),
            context={"mesh_path": mesh_path})


def find_nearest_cell_tool(mesh_path: str, *,
                            lat: float, lon: float,
                            convention: str = "auto",
                            adapter: Any) -> dict[str, Any]:
    """MCP-callable wrapper for find_nearest_cell."""
    from src.mcp.netcdf_reader import envelope
    ds, err = _open_mesh(mesh_path, adapter=adapter)
    if err:
        return err
    assert ds is not None
    try:
        resolved_conv = (convention if convention != "auto"
                         else _detect_convention(ds))
        _, _, _, cell_dim = _FAMILIES[resolved_conv]
        idx = find_nearest_cell(ds, lat=lat, lon=lon,
                                 convention=resolved_conv)
        lats, lons = _coords_deg(ds, resolved_conv)
        return envelope.success({
            "cell_index": idx,
            "actual_lat": float(lats[idx]),
            "actual_lon": float(lons[idx]),
            "mesh_path": mesh_path,
            "convention": resolved_conv,
            "cell_dim": cell_dim,
            "n_cells": int(ds.sizes[cell_dim]),
        })
    finally:
        ds.close()


def cells_in_bbox_tool(mesh_path: str, *,
                        lat_min: float, lat_max: float,
                        lon_min: float, lon_max: float,
                        convention: str = "auto",
                        adapter: Any) -> dict[str, Any]:
    """MCP-callable wrapper for cells_in_bbox."""
    from src.mcp.netcdf_reader import envelope
    ds, err = _open_mesh(mesh_path, adapter=adapter)
    if err:
        return err
    assert ds is not None
    try:
        resolved_conv = (convention if convention != "auto"
                         else _detect_convention(ds))
        _, _, _, cell_dim = _FAMILIES[resolved_conv]
        idx = cells_in_bbox(
            ds, lat_min=lat_min, lat_max=lat_max,
            lon_min=lon_min, lon_max=lon_max,
            convention=resolved_conv)
        return envelope.success({
            "cell_indices": idx.tolist(),
            "n_cells_in_bbox": int(idx.size),
            "mesh_path": mesh_path,
            "convention": resolved_conv,
            "cell_dim": cell_dim,
            "n_cells_total": int(ds.sizes[cell_dim]),
            "bbox": {"lat_min": lat_min, "lat_max": lat_max,
                     "lon_min": lon_min, "lon_max": lon_max},
        })
    finally:
        ds.close()

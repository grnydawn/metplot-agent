"""Cycle 11 — selector helpers for unstructured-mesh time-series /
profile workflows.

Three helpers feed the cycle-11 skill-side spatial reduction:

  find_nearest_cell(mesh_ds, lat, lon) -> int
    Great-circle (haversine) distance from (lat, lon) to every
    (latCell, lonCell). Returns the int index of the nearest.

  cells_in_bbox(mesh_ds, lat_min, lat_max, lon_min, lon_max)
                                                  -> np.ndarray[int]
    Cell indices whose center falls in the bbox. Handles
    cross-dateline (lon_min > lon_max) the same way cycle-3
    rectilinear region clipping does.

  area_weights(mesh_ds, indices=None) -> np.ndarray
    Returns 1-D weights array. Uses areaCell if present; uniform
    fallback otherwise.

All helpers handle MPAS radian/degree convention via the same
heuristic as `conventions/mpas.py:_to_degrees_if_radians`.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.mpas import _to_degrees_if_radians

_EARTH_RADIUS_KM = 6371.0


def _coords_deg(mesh_ds: xr.Dataset) -> tuple[np.ndarray, np.ndarray]:
    """Pull latCell / lonCell as 1-D degree arrays, applying the
    cycle-9 radian-detection heuristic."""
    lat = _to_degrees_if_radians(
        np.asarray(mesh_ds["latCell"].values, dtype=float),
        mesh_ds["latCell"].attrs)
    lon = _to_degrees_if_radians(
        np.asarray(mesh_ds["lonCell"].values, dtype=float),
        mesh_ds["lonCell"].attrs)
    return lat, lon


def find_nearest_cell(mesh_ds: xr.Dataset, *,
                       lat: float, lon: float) -> int:
    """Return the integer cell index whose great-circle distance to
    (lat, lon) is minimal. (lat, lon) are in degrees."""
    lats, lons = _coords_deg(mesh_ds)
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
                    lon_min: float, lon_max: float) -> np.ndarray:
    """Return cell indices whose (latCell, lonCell) center falls in
    the bbox. Cross-dateline bboxes (lon_min > lon_max) wrap.

    Lon convention agnostic: callers can supply either 0..360 or
    -180..180. The bbox compares against the mesh's lon coords as
    they are (after the radian-to-degree conversion); cross-
    dateline detection is purely numeric (lon_min > lon_max).
    """
    lats, lons = _coords_deg(mesh_ds)
    lat_ok = (lats >= lat_min) & (lats <= lat_max)
    if lon_min <= lon_max:
        lon_ok = (lons >= lon_min) & (lons <= lon_max)
    else:
        # Cross-dateline: union of [lon_min, +inf) and (-inf, lon_max].
        lon_ok = (lons >= lon_min) | (lons <= lon_max)
    return np.where(lat_ok & lon_ok)[0].astype(np.int64)


def area_weights(mesh_ds: xr.Dataset, *,
                  indices: np.ndarray | None = None) -> np.ndarray:
    """Return per-cell weights. Uses areaCell when present; uniform
    fallback otherwise. Subset to `indices` when supplied.

    Callers normalize as needed (weights.sum() may be != 1).
    """
    if "areaCell" in mesh_ds.variables:
        w = np.asarray(mesh_ds["areaCell"].values, dtype=float)
    else:
        n = int(mesh_ds.sizes["nCells"])
        w = np.ones(n, dtype=float)
    if indices is not None:
        w = w[np.asarray(indices)]
    return w

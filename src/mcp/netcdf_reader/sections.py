# src/mcp/netcdf_reader/sections.py
"""Cycle 13 theme D — great-circle cross-section sampler.

slice_along_section(mesh_ds, lat1, lon1, lat2, lon2, n_samples)
samples n equally-spaced points along the great-circle arc from
(lat1, lon1) to (lat2, lon2) and returns:

  * cell_indices: list[int] — nearest cell on the mesh at each
                              sample.
  * coords: list[tuple[float, float]] — the sample (lat, lon).
  * distances_km: list[float] — cumulative great-circle
                                 distance from sample 0.

Pure geometry — no data read. The renderer / skill picks up
the cell indices, fetches values via read_slice(cell_index=...),
and pcolormeshes against `distances_km` × `vertical_coord`.

Family-aware via the cycle-13 `convention=` hint (cycle 11
helpers): MPAS / CICE / EAMxx all work transparently.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify
from src.mcp.netcdf_reader.selectors_unstructured import (
    _FAMILIES, _coords_deg, _detect_convention,
    find_nearest_cell,
)

_EARTH_RADIUS_KM = 6371.0


def _great_circle_samples(lat1: float, lon1: float,
                            lat2: float, lon2: float,
                            n: int) -> tuple[np.ndarray, np.ndarray,
                                              np.ndarray]:
    """Slerp on the unit sphere — n equally-spaced points along
    the great-circle from (lat1, lon1) to (lat2, lon2).

    Returns (lats_deg, lons_deg, cum_dist_km).
    """
    p1_lat = np.radians(lat1)
    p1_lon = np.radians(lon1)
    p2_lat = np.radians(lat2)
    p2_lon = np.radians(lon2)
    # Cartesian on the unit sphere
    p1 = np.array([np.cos(p1_lat) * np.cos(p1_lon),
                    np.cos(p1_lat) * np.sin(p1_lon),
                    np.sin(p1_lat)])
    p2 = np.array([np.cos(p2_lat) * np.cos(p2_lon),
                    np.cos(p2_lat) * np.sin(p2_lon),
                    np.sin(p2_lat)])
    # Angle between p1 and p2 (slerp central angle)
    cos_omega = float(np.clip(np.dot(p1, p2), -1.0, 1.0))
    omega = np.arccos(cos_omega)
    # If endpoints coincide (degenerate), caller should detect.
    if omega < 1e-12:
        raise ValueError(
            "section endpoints coincide; supply distinct "
            "(lat1, lon1) and (lat2, lon2)")
    t = np.linspace(0.0, 1.0, n)
    sin_omega = np.sin(omega)
    a = np.sin((1 - t) * omega) / sin_omega
    b = np.sin(t * omega) / sin_omega
    points = (a[:, None] * p1) + (b[:, None] * p2)  # (n, 3)
    # Back to lat/lon
    lats = np.degrees(np.arcsin(np.clip(points[:, 2], -1.0, 1.0)))
    lons = np.degrees(np.arctan2(points[:, 1], points[:, 0]))
    # Cumulative arc-length on the unit sphere
    cum_arc = t * omega  # radians from start
    cum_km = cum_arc * _EARTH_RADIUS_KM
    return lats, lons, cum_km


def slice_along_section(mesh_ds: xr.Dataset, *,
                          lat1: float, lon1: float,
                          lat2: float, lon2: float,
                          n_samples: int,
                          convention: str = "auto"
                          ) -> dict[str, Any]:
    """See module docstring."""
    if n_samples < 2:
        raise ValueError(
            f"n_samples must be >= 2; got {n_samples}")
    if lat1 == lat2 and lon1 == lon2:
        raise ValueError(
            "section endpoints coincide; supply distinct "
            "(lat1, lon1) and (lat2, lon2)")

    lats, lons, cum_km = _great_circle_samples(
        lat1, lon1, lat2, lon2, n_samples)

    # Resolve convention once so we don't sniff per-sample.
    if convention == "auto":
        convention = _detect_convention(mesh_ds)
    _, _, _, cell_dim = _FAMILIES[convention]

    # For each sample, nearest cell. (n_samples is small; per-call
    # haversine over n_cells is fine. Optimize later if needed.)
    indices: list[int] = []
    for la, lo in zip(lats.tolist(), lons.tolist()):
        idx = find_nearest_cell(mesh_ds, lat=la, lon=lo,
                                  convention=convention)
        indices.append(int(idx))

    return {
        "cell_indices": indices,
        "coords": list(zip(lats.tolist(), lons.tolist())),
        "distances_km": cum_km.tolist(),
        "convention": convention,
        "cell_dim": cell_dim,
        "n_samples": n_samples,
    }


def slice_along_section_tool(mesh_path: str, *,
                               lat1: float, lon1: float,
                               lat2: float, lon2: float,
                               n_samples: int,
                               convention: str = "auto",
                               adapter: Any) -> dict[str, Any]:
    """MCP-callable wrapper. Opens the mesh, calls the sampler,
    wraps in an envelope."""
    try:
        cls = classify(mesh_path)
    except ClassifyError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"mesh_path": mesh_path})
    try:
        ds = adapter.open(cls.paths or [mesh_path])
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"mesh_path": mesh_path})
    try:
        try:
            out = slice_along_section(
                ds, lat1=lat1, lon1=lon1, lat2=lat2, lon2=lon2,
                n_samples=n_samples, convention=convention)
        except ValueError as e:
            return envelope.error(
                "invalid_spec", str(e),
                context={"endpoints": [(lat1, lon1), (lat2, lon2)],
                         "n_samples": n_samples})
        out["mesh_path"] = mesh_path
        return envelope.success(out)
    finally:
        ds.close()

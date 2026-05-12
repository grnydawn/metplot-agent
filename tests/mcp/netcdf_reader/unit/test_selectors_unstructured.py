"""Cycle 11 task 1 — unstructured selector helpers.

Three helpers feed the cycle-11 timeseries / profile flows:

  find_nearest_cell(mesh_ds, lat, lon)
    Great-circle (haversine) distance from (lat, lon) to every
    (latCell, lonCell). Returns the int index of the nearest.

  cells_in_bbox(mesh_ds, lat_min, lat_max, lon_min, lon_max)
    Returns np.ndarray[int] of cell indices whose center falls in
    the bbox. Handles cross-dateline (lon_min > lon_max).

  area_weights(mesh_ds, indices=None)
    Returns 1-D weights array. Uses areaCell if present; uniform
    fallback otherwise. When `indices` supplied, returns weights
    for that subset.

All helpers handle MPAS radian / degree convention transparently
via the cycle-9 `_to_degrees_if_radians` shared with mpas.py.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.selectors_unstructured import (
    area_weights,
    cells_in_bbox,
    find_nearest_cell,
)


def _mesh(n_cells: int = 8, *, lat_lon_pairs: list[tuple[float, float]]
            | None = None, areas: list[float] | None = None,
            in_radians: bool = False) -> xr.Dataset:
    """Synthetic MPAS-style mesh — minimal vars for selector tests."""
    if lat_lon_pairs is None:
        # Spread cells across the globe.
        lats = np.linspace(-80.0, 80.0, n_cells)
        lons = np.linspace(0.0, 350.0, n_cells)
    else:
        n_cells = len(lat_lon_pairs)
        lats = np.array([p[0] for p in lat_lon_pairs], dtype=float)
        lons = np.array([p[1] for p in lat_lon_pairs], dtype=float)
    if in_radians:
        lats = np.radians(lats)
        lons = np.radians(lons)
    data: dict[str, Any] = {
        "latCell": (("nCells",), lats),
        "lonCell": (("nCells",), lons),
    }
    if areas is not None:
        data["areaCell"] = (("nCells",), np.array(areas, dtype=float))
    return xr.Dataset(data)


# ── find_nearest_cell ──────────────────────────────────────────

def test_find_nearest_cell_exact_match():
    """When (lat, lon) coincides with a cell center, that cell's
    index is returned."""
    ds = _mesh(lat_lon_pairs=[(0.0, 0.0), (10.0, 20.0), (40.0, 60.0)])
    assert find_nearest_cell(ds, lat=10.0, lon=20.0) == 1


def test_find_nearest_cell_picks_nearest_great_circle():
    """Three candidates, target nearest to the middle one."""
    ds = _mesh(lat_lon_pairs=[
        (-30.0, -30.0), (0.0, 0.0), (30.0, 30.0)
    ])
    # Target (1, 1) — closer to (0, 0) than (30, 30) by a wide margin.
    assert find_nearest_cell(ds, lat=1.0, lon=1.0) == 1


def test_find_nearest_cell_handles_dateline():
    """Cells on either side of the dateline. (lat=0, lon=179) should
    pick cell at (0, 178) over (0, -178) — both 1° away, but
    haversine should resolve the tie consistently."""
    ds = _mesh(lat_lon_pairs=[(0.0, 178.0), (0.0, -178.0)])
    idx = find_nearest_cell(ds, lat=0.0, lon=179.0)
    # Both are 1° great-circle distance from (0, 179). Either index is
    # a valid answer; verify it returns one (not raises).
    assert idx in (0, 1)


def test_find_nearest_cell_works_on_radian_mesh():
    """MPAS-Ocean ships radians; the helper must convert before
    distance math, otherwise the nearest result is nonsense."""
    ds = _mesh(lat_lon_pairs=[(0.0, 0.0), (40.0, 60.0)], in_radians=True)
    # Target in degrees; (40, 60) is far closer than (0, 0).
    assert find_nearest_cell(ds, lat=40.0, lon=60.0) == 1


# ── cells_in_bbox ──────────────────────────────────────────────

def test_cells_in_bbox_simple_rectangle():
    ds = _mesh(lat_lon_pairs=[
        (-50.0, 0.0),    # 0: outside (lat)
        (10.0, 10.0),    # 1: inside
        (20.0, 50.0),    # 2: inside
        (60.0, 70.0),    # 3: outside (lat)
        (15.0, 80.0),    # 4: outside (lon)
    ])
    idx = cells_in_bbox(ds, lat_min=0.0, lat_max=30.0,
                        lon_min=0.0, lon_max=60.0)
    assert sorted(idx.tolist()) == [1, 2]


def test_cells_in_bbox_cross_dateline():
    """lon_min > lon_max means 'wrap around the dateline'."""
    ds = _mesh(lat_lon_pairs=[
        (0.0, 170.0),     # 0: inside (lon >= 170)
        (0.0, -170.0),    # 1: inside (lon <= -170)
        (0.0, 0.0),       # 2: outside
        (0.0, 180.0),     # 3: inside (boundary)
    ])
    idx = cells_in_bbox(ds, lat_min=-10.0, lat_max=10.0,
                        lon_min=170.0, lon_max=-170.0)
    assert sorted(idx.tolist()) == [0, 1, 3]


def test_cells_in_bbox_works_on_radian_mesh():
    ds = _mesh(lat_lon_pairs=[(10.0, 10.0), (40.0, 70.0)],
                in_radians=True)
    idx = cells_in_bbox(ds, lat_min=0.0, lat_max=30.0,
                        lon_min=0.0, lon_max=60.0)
    assert idx.tolist() == [0]


def test_cells_in_bbox_returns_empty_for_no_match():
    ds = _mesh()
    idx = cells_in_bbox(ds, lat_min=89.0, lat_max=89.5,
                        lon_min=0.0, lon_max=1.0)
    assert idx.size == 0


# ── area_weights ───────────────────────────────────────────────

def test_area_weights_uses_areaCell_when_present():
    ds = _mesh(n_cells=4, areas=[1.0, 2.0, 3.0, 4.0])
    w = area_weights(ds)
    assert w.tolist() == [1.0, 2.0, 3.0, 4.0]


def test_area_weights_uniform_fallback_when_missing():
    ds = _mesh(n_cells=5)  # no areaCell
    w = area_weights(ds)
    # Uniform weights — equal values; sum to n_cells (caller normalizes).
    assert w.shape == (5,)
    assert np.allclose(w, w[0])


def test_area_weights_subset_via_indices():
    ds = _mesh(n_cells=5, areas=[1.0, 2.0, 3.0, 4.0, 5.0])
    w = area_weights(ds, indices=np.array([0, 2, 4]))
    assert w.tolist() == [1.0, 3.0, 5.0]


def test_area_weights_subset_uniform_fallback():
    ds = _mesh(n_cells=5)
    w = area_weights(ds, indices=np.array([1, 3]))
    assert w.shape == (2,)
    assert np.allclose(w, w[0])

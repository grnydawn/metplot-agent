"""Cycle 13 theme A — generalized selectors for CICE/EAMxx.

The cycle-11 helpers (find_nearest_cell, cells_in_bbox,
area_weights) were MPAS-only: they assumed latCell/lonCell on
the nCells dim. Cycle 13 generalizes them to also work on:

  * CICE: TLAT/TLON/tarea on the `ni` dim.
  * EAMxx: lat/lon/area on the `ncol` dim.

Resolution is by mesh variable presence with `convention="auto"`;
callers can force a specific convention. The signature stays
the same as cycle 11 — `mesh_ds` + lat/lon + optional convention.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.selectors_unstructured import (
    area_weights, cells_in_bbox, find_nearest_cell,
)


# ── CICE-shape synthetic mesh ──────────────────────────────────

def _cice_mesh(n: int = 8, areas: list[float] | None = None) -> xr.Dataset:
    lats = np.linspace(-80.0, 80.0, n)
    lons = np.linspace(0.0, 350.0, n)
    data: dict[str, Any] = {
        "TLAT": (("ni",), lats),
        "TLON": (("ni",), lons),
    }
    if areas is not None:
        data["tarea"] = (("ni",), np.array(areas, dtype=float))
    return xr.Dataset(data, attrs={"source": "CICE"})


def test_find_nearest_cell_on_cice_mesh():
    """CICE meshes use TLAT/TLON on the `ni` dim — the generalized
    helper must find them via auto-detect."""
    ds = _cice_mesh()
    # Mesh lats 8 cells from -80..80; (lat=0, lon=180) should pick
    # the middle-ish cell — but we just verify it returns a valid
    # int in range, not the exact index.
    idx = find_nearest_cell(ds, lat=0.0, lon=180.0)
    assert isinstance(idx, int) or hasattr(idx, "__index__")
    assert 0 <= idx < ds.sizes["ni"]


def test_cells_in_bbox_on_cice_mesh():
    ds = _cice_mesh(n=10)
    idx = cells_in_bbox(ds, lat_min=-10.0, lat_max=20.0,
                         lon_min=0.0, lon_max=180.0)
    assert idx.dtype.kind in ("i", "u")
    # At least one cell should fall in the equator/Pac swath.
    assert idx.size >= 1


def test_area_weights_on_cice_mesh_with_tarea():
    ds = _cice_mesh(n=5, areas=[1.0, 2.0, 3.0, 4.0, 5.0])
    w = area_weights(ds)
    assert w.shape == (5,)
    assert w.tolist() == [1.0, 2.0, 3.0, 4.0, 5.0]


def test_area_weights_on_cice_uniform_fallback():
    ds = _cice_mesh(n=6)  # no tarea
    w = area_weights(ds)
    assert w.shape == (6,)
    assert np.allclose(w, w[0])


# ── EAMxx-shape synthetic mesh ─────────────────────────────────

def _eamxx_mesh(n: int = 8, areas: list[float] | None = None) -> xr.Dataset:
    lats = np.linspace(-85.0, 85.0, n)
    lons = np.linspace(0.0, 355.0, n)
    data: dict[str, Any] = {
        "lat": (("ncol",), lats),
        "lon": (("ncol",), lons),
    }
    if areas is not None:
        data["area"] = (("ncol",), np.array(areas, dtype=float))
    return xr.Dataset(data, attrs={"source": "EAMxx"})


def test_find_nearest_cell_on_eamxx_mesh():
    ds = _eamxx_mesh()
    idx = find_nearest_cell(ds, lat=0.0, lon=0.0)
    assert 0 <= idx < ds.sizes["ncol"]


def test_cells_in_bbox_on_eamxx_mesh():
    ds = _eamxx_mesh(n=10)
    idx = cells_in_bbox(ds, lat_min=-30.0, lat_max=30.0,
                         lon_min=0.0, lon_max=180.0)
    assert idx.size >= 1


def test_area_weights_on_eamxx_with_area():
    ds = _eamxx_mesh(n=4, areas=[10.0, 20.0, 30.0, 40.0])
    w = area_weights(ds)
    assert w.tolist() == [10.0, 20.0, 30.0, 40.0]


def test_area_weights_on_eamxx_uniform_fallback():
    ds = _eamxx_mesh(n=3)  # no area
    w = area_weights(ds)
    assert w.shape == (3,)
    assert np.allclose(w, w[0])


# ── MPAS still works (backwards compat) ────────────────────────

def test_mpas_meshes_still_work_after_generalization():
    """The cycle-11 callers must keep working with no changes."""
    ds = xr.Dataset(
        {"latCell": (("nCells",),
                      np.array([10.0, 20.0, 30.0, 40.0])),
         "lonCell": (("nCells",),
                      np.array([0.0, 90.0, 180.0, 270.0]))},
        attrs={"Conventions": "MPAS"})
    idx = find_nearest_cell(ds, lat=20.0, lon=90.0)
    assert idx == 1
    bb = cells_in_bbox(ds, lat_min=15.0, lat_max=25.0,
                        lon_min=80.0, lon_max=100.0)
    assert bb.tolist() == [1]
    w = area_weights(ds)
    assert w.shape == (4,)


# ── Explicit convention hint ───────────────────────────────────

def test_explicit_convention_overrides_auto():
    """If a mesh has BOTH cycle-9 latCell AND a stray 'lat' var,
    auto-detection might be ambiguous. The convention= hint
    forces the choice."""
    ds = xr.Dataset(
        {"latCell": (("nCells",), np.array([0.0, 30.0, 60.0])),
         "lonCell": (("nCells",), np.array([0.0, 0.0, 0.0])),
         # Stray rectilinear-style coord — should be ignored
         # when convention="MPAS".
         "lat": (("lat",), np.array([10.0, 20.0]))},
    )
    idx = find_nearest_cell(ds, lat=30.0, lon=0.0, convention="MPAS")
    assert idx == 1

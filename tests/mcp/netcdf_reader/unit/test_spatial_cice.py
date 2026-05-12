"""CICE spatial extraction — paired history + grid file.

A CICE restart alone has no coordinates. Geometry comes from a
separate CICE grid file (`grid.nc`, `pop_grid.nc`, etc.) that
ships TLAT(nj, ni) and TLON(nj, ni) as cell-center degrees.

These tests pin extract_spatial_cice's contract: validate the
(nj, ni) shapes are compatible (either matching directly or
matching after history-flattening), surface the unstructured
envelope keyed on `ni`, populate vertex bounds when present,
and refuse to fabricate geometry when the dim shapes don't agree.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.cice import extract_spatial_cice


def _cice_grid_dataset(nj: int = 4, ni: int = 6, *, with_bounds: bool = False
                       ) -> xr.Dataset:
    """Synthetic CICE grid file — TLAT/TLON degrees on (nj, ni)."""
    # Construct lat/lon so the convention check picks 0..360 vs -180..180
    # cleanly: span [-80, 80] in lat and [0, 350] in lon.
    lat_1d = np.linspace(-80.0, 80.0, nj)
    lon_1d = np.linspace(0.0, 350.0, ni)
    tlat = np.broadcast_to(lat_1d[:, None], (nj, ni)).copy()
    tlon = np.broadcast_to(lon_1d[None, :], (nj, ni)).copy()
    data: dict[str, Any] = {
        "TLAT": (("nj", "ni"), tlat),
        "TLON": (("nj", "ni"), tlon),
    }
    if with_bounds:
        ncorners = 4
        data["latt_bounds"] = (
            ("nj", "ni", "nvertices"),
            np.zeros((nj, ni, ncorners)),
        )
        data["lont_bounds"] = (
            ("nj", "ni", "nvertices"),
            np.zeros((nj, ni, ncorners)),
        )
    return xr.Dataset(data)


def _cice_history_dataset_flattened(n_cells: int = 24) -> xr.Dataset:
    """Synthetic CICE restart — flattened (nj=1, ni=N)."""
    return xr.Dataset(
        {
            "aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "vicen": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "Tsfcn": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
        }
    )


def _cice_history_dataset_2d(nj: int = 4, ni: int = 6) -> xr.Dataset:
    """Synthetic CICE history — non-flattened (nj=N, ni=M)."""
    return xr.Dataset(
        {
            "aicen": (("ncat", "nj", "ni"), np.zeros((1, nj, ni))),
            "Tsfcn": (("ncat", "nj", "ni"), np.zeros((1, nj, ni))),
        }
    )


def test_paired_extraction_direct_shape():
    """Non-flattened history + matching grid → unstructured envelope
    with n_cells = nj * ni, lat/lon vars TLAT/TLON, lon convention
    auto-detected."""
    grid = _cice_grid_dataset(nj=4, ni=6)
    hist = _cice_history_dataset_2d(nj=4, ni=6)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["coord_kind"] == "unstructured"
    assert spatial["cell_dim"] == "ni"
    assert spatial["n_cells"] == 24
    assert spatial["lat_var"] == "TLAT"
    assert spatial["lon_var"] == "TLON"
    assert spatial["lon_convention"] == "0..360"


def test_paired_extraction_flattened_history():
    """Flattened (nj=1, ni=24) history + grid (nj=4, ni=6) →
    n_cells=24 still works; the 4*6=24 product check passes."""
    grid = _cice_grid_dataset(nj=4, ni=6)
    hist = _cice_history_dataset_flattened(n_cells=24)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["n_cells"] == 24


def test_paired_extraction_records_2d_grid_shape_hint():
    """Renderer needs to know the (nj, ni) shape so it can
    pcolormesh-reshape later. Cycle-9 spec §3.4: pcolormesh is the
    preferred CICE render path."""
    grid = _cice_grid_dataset(nj=4, ni=6)
    hist = _cice_history_dataset_2d(nj=4, ni=6)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["grid_shape_2d"] == [4, 6]


def test_paired_extraction_mismatch_returns_none():
    """History (nj=2, ni=10) → product 20; grid (nj=4, ni=6) → product
    24. The pair is incompatible; extractor must refuse."""
    grid = _cice_grid_dataset(nj=4, ni=6)
    hist = _cice_history_dataset_2d(nj=2, ni=10)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is None


def test_paired_extraction_grid_without_tlat_returns_none():
    """A 'grid' file missing TLAT can't pair — return None so the
    caller surfaces a usable error rather than fabricating geometry."""
    grid = xr.Dataset(
        {"ULON": (("nj", "ni"), np.zeros((4, 6)))},
    )
    hist = _cice_history_dataset_flattened(n_cells=24)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is None


def test_paired_extraction_vertex_bounds_populated_when_present():
    grid = _cice_grid_dataset(nj=4, ni=6, with_bounds=True)
    hist = _cice_history_dataset_flattened(n_cells=24)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["vertex_lat_var"] == "latt_bounds"
    assert spatial["vertex_lon_var"] == "lont_bounds"


def test_paired_extraction_vertex_bounds_absent_returns_none_for_vertices():
    grid = _cice_grid_dataset(nj=4, ni=6, with_bounds=False)
    hist = _cice_history_dataset_flattened(n_cells=24)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["vertex_lat_var"] is None
    assert spatial["vertex_lon_var"] is None
    assert spatial["vertices_on_cell_var"] is None


def test_paired_extraction_negative_lon_convention():
    """Lon in [-180, 180] convention → lon_convention = '-180..180'."""
    nj, ni = 4, 6
    tlat = np.broadcast_to(np.linspace(-80, 80, nj)[:, None], (nj, ni)).copy()
    tlon = np.broadcast_to(np.linspace(-170, 170, ni)[None, :], (nj, ni)).copy()
    grid = xr.Dataset(
        {
            "TLAT": (("nj", "ni"), tlat),
            "TLON": (("nj", "ni"), tlon),
        }
    )
    hist = _cice_history_dataset_flattened(n_cells=nj * ni)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["lon_convention"] == "-180..180"


def test_paired_extraction_lat_lon_ranges():
    grid = _cice_grid_dataset(nj=4, ni=6)
    hist = _cice_history_dataset_2d(nj=4, ni=6)
    spatial = extract_spatial_cice(hist, grid)
    assert spatial is not None
    assert spatial["lat_range"] == [-80.0, 80.0]
    # lon goes 0..350 in this fixture
    assert spatial["lon_range"][0] == 0.0
    assert spatial["lon_range"][1] == 350.0

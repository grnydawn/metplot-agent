"""EAMxx physics-grid spatial extraction.

EAMxx physics output ships on a 1-D `ncol` axis. The geometry
lives in a separate scrip-style file with `lat[ncol]`, `lon[ncol]`
and optional `grid_corner_lat[ncol, ncorners]` /
`grid_corner_lon[ncol, ncorners]` vertex bounds.

These tests pin extract_spatial_eamxx: validate ncol agreement
between history and grid, surface the unstructured envelope keyed
on `ncol`, populate vertex bounds when present, refuse when the
grid file ships 2-D lat (SCRIP-bounds-only without centers), and
refuse on dim mismatch.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.eamxx import extract_spatial_eamxx


def _eamxx_phys_grid(ncol: int = 100, *, with_corners: bool = False
                      ) -> xr.Dataset:
    """Synthetic SCRIP-style EAMxx physics grid file."""
    rng = np.random.default_rng(0)
    lat = rng.uniform(-90.0, 90.0, size=ncol)
    lon = rng.uniform(0.0, 360.0, size=ncol)
    data: dict[str, Any] = {
        "lat": (("ncol",), lat),
        "lon": (("ncol",), lon),
    }
    if with_corners:
        ncorners = 4
        data["grid_corner_lat"] = (
            ("ncol", "ncorners"),
            np.zeros((ncol, ncorners)),
        )
        data["grid_corner_lon"] = (
            ("ncol", "ncorners"),
            np.zeros((ncol, ncorners)),
        )
    return xr.Dataset(data)


def _eamxx_history(ncol: int = 100) -> xr.Dataset:
    """Synthetic EAMxx physics-axis history (T_mid, ps)."""
    return xr.Dataset(
        {
            "T_mid": (("time", "ncol", "lev"), np.zeros((1, ncol, 8))),
            "ps": (("time", "ncol"), np.zeros((1, ncol))),
        }
    )


def test_paired_extraction_basic():
    grid = _eamxx_phys_grid(ncol=100)
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is not None
    assert spatial["coord_kind"] == "unstructured"
    assert spatial["cell_dim"] == "ncol"
    assert spatial["n_cells"] == 100
    assert spatial["lat_var"] == "lat"
    assert spatial["lon_var"] == "lon"


def test_paired_extraction_ncol_mismatch_returns_none():
    """A grid file with 200 cells can't pair with a 100-cell history."""
    grid = _eamxx_phys_grid(ncol=200)
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is None


def test_paired_extraction_grid_without_ncol_returns_none():
    """A grid file with no `ncol` dim can't be an EAMxx physics grid
    — refuse cleanly."""
    grid = xr.Dataset(
        {"lat": (("x",), np.linspace(-90, 90, 10)),
         "lon": (("x",), np.linspace(0, 360, 10))}
    )
    hist = _eamxx_history(ncol=10)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is None


def test_paired_extraction_grid_without_lat_returns_none():
    grid = xr.Dataset({"lon": (("ncol",), np.zeros(100))})
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is None


def test_paired_extraction_vertex_bounds_populated_when_present():
    grid = _eamxx_phys_grid(ncol=100, with_corners=True)
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is not None
    assert spatial["vertex_lat_var"] == "grid_corner_lat"
    assert spatial["vertex_lon_var"] == "grid_corner_lon"


def test_paired_extraction_vertex_bounds_absent_returns_none_for_vertices():
    grid = _eamxx_phys_grid(ncol=100, with_corners=False)
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is not None
    assert spatial["vertex_lat_var"] is None
    assert spatial["vertex_lon_var"] is None


def test_paired_extraction_lon_convention_0_360():
    """All-positive lon → 0..360 convention."""
    grid = _eamxx_phys_grid(ncol=100)  # rng default produces [0, 360)
    hist = _eamxx_history(ncol=100)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is not None
    assert spatial["lon_convention"] == "0..360"


def test_paired_extraction_lon_convention_negative():
    """Negative lon values → -180..180 convention."""
    grid = xr.Dataset(
        {
            "lat": (("ncol",), np.linspace(-90, 90, 10)),
            "lon": (("ncol",), np.linspace(-170, 170, 10)),
        }
    )
    hist = xr.Dataset({"T_mid": (("ncol",), np.zeros(10))})
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is not None
    assert spatial["lon_convention"] == "-180..180"


def test_paired_extraction_2d_lat_returns_none():
    """SCRIP-bounds-only grid (lat ships as 2-D corner-set, no
    1-D centers) is rejected cleanly. Caller surfaces a usable
    error rather than the extractor producing geometry with
    mis-shaped lat/lon."""
    ncol = 10
    grid = xr.Dataset(
        {
            "lat": (("ncol", "ncorners"), np.zeros((ncol, 4))),
            "lon": (("ncol", "ncorners"), np.zeros((ncol, 4))),
        }
    )
    hist = _eamxx_history(ncol=ncol)
    spatial = extract_spatial_eamxx(hist, grid)
    assert spatial is None

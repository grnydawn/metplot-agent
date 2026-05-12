"""Cycle 13 theme D — slice_along_section pure-numpy sampler.

slice_along_section(mesh_ds, lat1, lon1, lat2, lon2, n_samples)
samples n points along the great-circle arc from (lat1, lon1)
to (lat2, lon2) and returns the nearest cell at each sample.
The result also carries cumulative great-circle distance in km
so the renderer can plot a real-world x-axis.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.sections import slice_along_section


def _mpas_mesh(n: int = 20) -> xr.Dataset:
    """Synthetic MPAS-shape mesh spread across the globe."""
    lats = np.linspace(-80.0, 80.0, n)
    lons = np.linspace(0.0, 350.0, n)
    return xr.Dataset(
        {"latCell": (("nCells",), lats),
         "lonCell": (("nCells",), lons)},
        attrs={"Conventions": "MPAS"})


def test_endpoint_nearest_cells_returned():
    """Section from (0, 0) to (60, 60) on a coarse mesh — first
    sample should pick the cell nearest (0, 0); last sample the
    cell nearest (60, 60)."""
    ds = _mpas_mesh(n=20)
    out = slice_along_section(ds, lat1=0, lon1=0, lat2=60, lon2=60,
                                n_samples=10)
    idx = out["cell_indices"]
    coords = out["coords"]
    assert len(idx) == 10
    # First sample at (0, 0), last at (60, 60)
    first_lat, first_lon = coords[0]
    last_lat, last_lon = coords[-1]
    assert abs(first_lat - 0.0) < 1e-9
    assert abs(first_lon - 0.0) < 1e-9
    assert abs(last_lat - 60.0) < 1e-9
    assert abs(last_lon - 60.0) < 1e-9


def test_distances_monotonic_increasing():
    ds = _mpas_mesh()
    out = slice_along_section(ds, lat1=-30, lon1=20, lat2=30, lon2=200,
                                n_samples=15)
    d = np.asarray(out["distances_km"])
    assert d[0] == 0.0
    diffs = np.diff(d)
    assert (diffs >= 0).all(), "cumulative distances must be non-decreasing"


def test_distance_endpoint_matches_haversine():
    """Total section length = great-circle from start to end."""
    ds = _mpas_mesh()
    out = slice_along_section(ds, lat1=0, lon1=0, lat2=0, lon2=180,
                                n_samples=20)
    d = out["distances_km"][-1]
    # 180° along the equator on a 6371 km sphere = π·R ≈ 20015 km
    expected = np.pi * 6371.0
    assert abs(d - expected) / expected < 1e-3


def test_n_samples_must_be_at_least_2():
    ds = _mpas_mesh()
    try:
        slice_along_section(ds, lat1=0, lon1=0, lat2=10, lon2=10,
                              n_samples=1)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_degenerate_endpoints_raises():
    """lat1==lat2 AND lon1==lon2 → zero-length section."""
    ds = _mpas_mesh()
    try:
        slice_along_section(ds, lat1=10, lon1=20, lat2=10, lon2=20,
                              n_samples=5)
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_works_on_cice_mesh():
    """Generalized to CICE family via convention="auto"."""
    ds = xr.Dataset(
        {"TLAT": (("ni",), np.linspace(-80.0, 80.0, 10)),
         "TLON": (("ni",), np.linspace(0.0, 350.0, 10))},
        attrs={"source": "CICE"})
    out = slice_along_section(ds, lat1=0, lon1=0, lat2=40, lon2=180,
                                n_samples=5)
    assert len(out["cell_indices"]) == 5
    # All indices must be valid ni range
    assert all(0 <= int(i) < 10 for i in out["cell_indices"])


def test_explicit_convention_overrides():
    """Force EAMxx parsing on a mesh that has both latCell and lat."""
    ds = xr.Dataset(
        {"latCell": (("nCells",), np.array([10.0, 20.0])),
         "lonCell": (("nCells",), np.array([0.0, 90.0])),
         "lat":     (("ncol",),    np.array([5.0, 25.0])),
         "lon":     (("ncol",),    np.array([30.0, 100.0]))})
    out = slice_along_section(ds, lat1=5, lon1=30, lat2=25, lon2=100,
                                n_samples=2, convention="EAMxx")
    # Sample 0 nearest (5, 30) → ncol index 0; sample 1 nearest
    # (25, 100) → ncol index 1.
    assert out["cell_indices"] == [0, 1]

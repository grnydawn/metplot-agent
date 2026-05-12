"""Mesh-pair heuristics extended to CICE + EAMxx (cycle 9 §3.3).

The cycle-8 module pairs MPAS history files with `_mesh.nc` /
`init.nc` siblings. Cycle 9 extends the candidate ranking to also
surface CICE grid files (`grid.nc`, `*_grid.nc`, `pop_grid*.nc`,
`gx*v*.nc`) and EAMxx physics-grid files (`*scrip*.nc`,
`*pg2*.nc`, `ne*lonlat*.nc`).

Validate also has to handle the new dim-shape pairings:
  - CICE: history.nj * history.ni == grid.nj * grid.ni
  - EAMxx: history.ncol == grid.ncol
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.paths.mesh_pair import (
    find_mesh_candidates, validate_mesh_pair,
)


def test_finds_cice_grid_nc(tmp_path):
    """A CICE restart sibling to a plain `grid.nc` should rank grid.nc
    as a candidate."""
    hist = tmp_path / "cice.r.0001-01-01.nc"
    hist.write_bytes(b"")
    grid = tmp_path / "grid.nc"
    grid.write_bytes(b"")
    candidates = find_mesh_candidates(hist)
    assert grid.resolve() in candidates, [str(c) for c in candidates]


def test_finds_cice_underscore_grid_nc(tmp_path):
    """`cice_grid.nc` / `pop_grid.nc` patterns should also surface."""
    hist = tmp_path / "cice.r.0001-01-01.nc"
    hist.write_bytes(b"")
    cgrid = tmp_path / "cice_grid.nc"
    cgrid.write_bytes(b"")
    pgrid = tmp_path / "pop_grid.nc"
    pgrid.write_bytes(b"")
    candidates = find_mesh_candidates(hist)
    paths_str = [str(c) for c in candidates]
    assert any("cice_grid" in p for p in paths_str), paths_str
    assert any("pop_grid" in p for p in paths_str), paths_str


def test_finds_eamxx_scrip(tmp_path):
    """EAMxx history file sibling to a scrip file should surface it."""
    hist = tmp_path / "eamxx.h0.0001-01-01-00000.nc"
    hist.write_bytes(b"")
    scrip = tmp_path / "ne30pg2_scrip.nc"
    scrip.write_bytes(b"")
    candidates = find_mesh_candidates(hist)
    assert scrip.resolve() in candidates, [str(c) for c in candidates]


def test_finds_eamxx_pg2_pattern(tmp_path):
    """ne*pg2*.nc and ne*lonlat*.nc patterns (the canonical SE2 phys
    grid filename family) should also surface."""
    hist = tmp_path / "eamxx.h0.0001.nc"
    hist.write_bytes(b"")
    pg = tmp_path / "ne1024pg2.nc"
    pg.write_bytes(b"")
    ll = tmp_path / "ne30pg2_lonlat.nc"
    ll.write_bytes(b"")
    candidates = find_mesh_candidates(hist)
    paths_str = [str(c) for c in candidates]
    assert any("ne1024pg2" in p for p in paths_str), paths_str
    assert any("lonlat" in p for p in paths_str), paths_str


def test_self_excluded_from_candidates(tmp_path):
    """A CICE restart matching one of the grid-file globs (unlikely
    but possible) must not list itself."""
    hist = tmp_path / "cice_grid_history.nc"
    hist.write_bytes(b"")
    candidates = find_mesh_candidates(hist)
    assert hist.resolve() not in candidates


def test_validate_pair_cice_flattened_ok():
    """CICE history flattened (nj=1, ni=24) + grid (nj=4, ni=6) →
    product matches → pair is valid (returns None)."""
    hist = xr.Dataset(
        {"aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, 24)))}
    )
    grid = xr.Dataset(
        {
            "TLAT": (("nj", "ni"), np.zeros((4, 6))),
            "TLON": (("nj", "ni"), np.zeros((4, 6))),
        }
    )
    err = validate_mesh_pair(hist, grid)
    assert err is None, f"expected valid pair; got {err!r}"


def test_validate_pair_cice_product_mismatch():
    """CICE history (nj=1, ni=20) + grid (nj=4, ni=6 → product 24)
    must error since 20 != 24."""
    hist = xr.Dataset(
        {"aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, 20)))}
    )
    grid = xr.Dataset(
        {
            "TLAT": (("nj", "ni"), np.zeros((4, 6))),
            "TLON": (("nj", "ni"), np.zeros((4, 6))),
        }
    )
    err = validate_mesh_pair(hist, grid)
    assert err is not None and "mismatch" in err.lower(), err


def test_validate_pair_eamxx_ok():
    hist = xr.Dataset(
        {"T_mid": (("time", "ncol", "lev"), np.zeros((1, 100, 8)))}
    )
    grid = xr.Dataset(
        {
            "lat": (("ncol",), np.zeros(100)),
            "lon": (("ncol",), np.zeros(100)),
        }
    )
    err = validate_mesh_pair(hist, grid)
    assert err is None, f"expected valid pair; got {err!r}"


def test_validate_pair_eamxx_ncol_mismatch():
    hist = xr.Dataset(
        {"T_mid": (("time", "ncol", "lev"), np.zeros((1, 100, 8)))}
    )
    grid = xr.Dataset(
        {
            "lat": (("ncol",), np.zeros(200)),
            "lon": (("ncol",), np.zeros(200)),
        }
    )
    err = validate_mesh_pair(hist, grid)
    assert err is not None and "ncol" in err.lower(), err


def test_validate_pair_mpas_still_works():
    """Regression: cycle-8 MPAS validation must keep working."""
    hist = xr.Dataset(
        {"Temperature": (("Time", "NCells"), np.zeros((1, 7)))}
    )
    mesh = xr.Dataset(
        {"latCell": (("nCells",), np.zeros(7)),
         "lonCell": (("nCells",), np.zeros(7))}
    )
    err = validate_mesh_pair(hist, mesh)
    assert err is None, f"MPAS pair must still validate; got {err!r}"

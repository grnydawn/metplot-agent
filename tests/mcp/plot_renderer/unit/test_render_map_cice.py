"""Cycle 9 task 9 — CICE pcolormesh renderer.

render_map with a CICE-shape spec (1-D values of length nj*ni +
mesh_path to a CICE grid file with TLAT/TLON) produces a
recognizable map via pcolormesh after 2-D reshape.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.plot_renderer.tools.render_map import render_map


def _cice_grid(tmp_path: Path, nj: int = 4, ni: int = 6) -> Path:
    lat_1d = np.linspace(-80.0, 80.0, nj)
    lon_1d = np.linspace(0.0, 350.0, ni)
    ds = xr.Dataset(
        {
            "TLAT": (("nj", "ni"),
                     np.broadcast_to(lat_1d[:, None],
                                     (nj, ni)).copy()),
            "TLON": (("nj", "ni"),
                     np.broadcast_to(lon_1d[None, :],
                                     (nj, ni)).copy()),
        }
    )
    p = tmp_path / "grid.nc"
    ds.to_netcdf(p)
    return p


def _make_spec(tmp_path: Path, values: np.ndarray,
                mesh_path: Path, **overrides) -> dict:
    return {
        "values": values.tolist(),
        "mesh_path": str(mesh_path),
        "output_path": str(tmp_path / "out.png"),
        "title": "CICE Tsfcn (test)",
        **overrides,
    }


def test_render_cice_pcolormesh_produces_png(tmp_path: Path):
    nj, ni = 4, 6
    mesh = _cice_grid(tmp_path, nj=nj, ni=ni)
    rng = np.random.default_rng(0)
    values = rng.uniform(-2, 2, size=nj * ni)
    env = render_map(_make_spec(tmp_path, values, mesh))
    assert env["ok"] is True, env.get("error")
    out = Path(env["result"]["output_path"])
    assert out.exists(), out
    assert out.stat().st_size > 1000  # non-trivial raster
    # Oracle drawn block must tag the grid_kind so audits can tell
    # which renderer ran.
    assert env["result"]["oracle"]["drawn"]["grid_kind"] == "unstructured_cice"
    assert env["result"]["oracle"]["drawn"]["n_cells"] == nj * ni


def test_render_cice_shape_mismatch_errors(tmp_path: Path):
    """Values length must equal nj*ni — otherwise shape_mismatch."""
    nj, ni = 4, 6
    mesh = _cice_grid(tmp_path, nj=nj, ni=ni)
    wrong = np.zeros(50)  # 50 ≠ 24
    env = render_map(_make_spec(tmp_path, wrong, mesh))
    assert env["ok"] is False
    assert env["error"]["code"] == "shape_mismatch"


def test_render_cice_missing_mesh_errors(tmp_path: Path):
    """Bad mesh_path → mesh_path_unreadable, not a crash."""
    rng = np.random.default_rng(0)
    values = rng.uniform(-2, 2, size=24)
    env = render_map({
        "values": values.tolist(),
        "mesh_path": str(tmp_path / "nope.nc"),
        "output_path": str(tmp_path / "out.png"),
    })
    assert env["ok"] is False
    assert env["error"]["code"] == "mesh_path_unreadable"

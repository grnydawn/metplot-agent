"""Cycle 9 task 9 — EAMxx physics-grid scatter renderer.

render_map with an EAMxx-shape spec (1-D values of length ncol +
mesh_path to a scrip-style grid file with lat[ncol]/lon[ncol])
produces a recognizable map via filled scatter.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.plot_renderer.tools.render_map import render_map


def _eamxx_phys_grid(tmp_path: Path, ncol: int = 100) -> Path:
    """Synthetic SCRIP-style EAMxx physics grid file."""
    rng = np.random.default_rng(0)
    lat = rng.uniform(-90.0, 90.0, size=ncol)
    lon = rng.uniform(0.0, 360.0, size=ncol)
    ds = xr.Dataset(
        {
            "lat": (("ncol",), lat),
            "lon": (("ncol",), lon),
        }
    )
    p = tmp_path / "ne_phys_grid.nc"
    ds.to_netcdf(p)
    return p


def _make_spec(tmp_path: Path, values: np.ndarray,
                mesh_path: Path, **overrides) -> dict:
    return {
        "values": values.tolist(),
        "mesh_path": str(mesh_path),
        "output_path": str(tmp_path / "out.png"),
        "title": "EAMxx T_mid (test)",
        **overrides,
    }


def test_render_eamxx_scatter_produces_png(tmp_path: Path):
    ncol = 100
    mesh = _eamxx_phys_grid(tmp_path, ncol=ncol)
    rng = np.random.default_rng(1)
    values = rng.uniform(220, 310, size=ncol)
    env = render_map(_make_spec(tmp_path, values, mesh))
    assert env["ok"] is True, env.get("error")
    out = Path(env["result"]["output_path"])
    assert out.exists()
    assert out.stat().st_size > 1000
    assert env["result"]["oracle"]["drawn"]["grid_kind"] == "unstructured_eamxx"
    assert env["result"]["oracle"]["drawn"]["n_cells"] == ncol


def test_render_eamxx_shape_mismatch_errors(tmp_path: Path):
    mesh = _eamxx_phys_grid(tmp_path, ncol=100)
    env = render_map(_make_spec(tmp_path, np.zeros(50), mesh))
    assert env["ok"] is False
    assert env["error"]["code"] == "shape_mismatch"


def test_render_dycore_refusal(tmp_path: Path):
    """Cycle 9 §3.4: a dycore-axis variable refuses with
    unstructured_dycore_unsupported, not a crash."""
    mesh = _eamxx_phys_grid(tmp_path, ncol=100)
    env = render_map({
        "values": np.zeros(9905 * 4 * 4).tolist(),
        "mesh_path": str(mesh),
        "grid_kind": "dycore_spectral",
        "output_path": str(tmp_path / "out.png"),
    })
    assert env["ok"] is False
    assert env["error"]["code"] == "unstructured_dycore_unsupported"

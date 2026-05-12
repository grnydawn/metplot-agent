"""Cycle 13 theme B — CPL single-domain scatter render.

E3SM coupler files carry multiple domain prefixes
(doma_, doml_, domo_, domi_ for atm / lnd / ocn / ice). MVP:
render one domain at a time; default = 'doma' (atmosphere);
caller may override via spec['domain'].
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.plot_renderer.tools.render_map import (
    _peek_grid_kind, render_map,
)


def _cpl_mesh(tmp_path: Path, n_x: int = 50) -> Path:
    """Synthetic CPL-shape mesh: doma_lat / doma_lon on
    (doma_ny=1, doma_nx)."""
    rng = np.random.default_rng(3)
    lats = rng.uniform(-89.5, 89.5, (1, n_x))
    lons = rng.uniform(-180.0, 180.0, (1, n_x))
    ds = xr.Dataset(
        {"doma_lat": (("doma_ny", "doma_nx"), lats,
                       {"units": "degrees_north"}),
         "doma_lon": (("doma_ny", "doma_nx"), lons,
                       {"units": "degrees_east"})},
        attrs={"file_version": "cpl7v10"})
    p = tmp_path / "cpl_mesh.nc"
    ds.to_netcdf(p)
    return p


def test_peek_grid_kind_detects_cpl(tmp_path: Path):
    mesh = _cpl_mesh(tmp_path)
    assert _peek_grid_kind(str(mesh)) == "cpl"


def test_render_cpl_scatter_produces_png(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mesh = _cpl_mesh(tmp_path, n_x=80)
    values = np.linspace(280.0, 310.0, 80)
    env = render_map({
        "values": values.tolist(),
        "mesh_path": str(mesh),
        "title": "CPL doma scatter",
    })
    assert env["ok"] is True, env.get("error")
    out_path = Path(env["result"]["output_path"])
    assert out_path.exists()
    assert out_path.stat().st_size > 5_000
    assert env["result"]["oracle"]["drawn"]["grid_kind"] == \
        "unstructured_cpl"
    assert env["result"]["oracle"]["drawn"]["n_cells"] == 80


def test_render_cpl_unknown_domain_errors(tmp_path: Path, monkeypatch):
    """Default is 'doma'; if user asks for 'domx' which doesn't
    exist, return a structured error."""
    monkeypatch.chdir(tmp_path)
    mesh = _cpl_mesh(tmp_path, n_x=80)
    env = render_map({
        "values": [0.0] * 80,
        "mesh_path": str(mesh),
        "domain": "domx",  # not in the file
    })
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "invalid_spec", "mesh_path_unreadable",
        "internal_render_error")

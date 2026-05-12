"""Cycle 13 theme B — ELM gridcell scatter render.

MVP: scatter at (latixy, longxy) on the gridcell dim. PFT /
column-level rendering is out of scope.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.plot_renderer.tools.render_map import (
    _peek_grid_kind, render_map,
)


def _elm_mesh(tmp_path: Path, n: int = 50) -> Path:
    """Synthetic ELM-shape mesh: latixy + longxy on gridcell."""
    rng = np.random.default_rng(2)
    lats = rng.uniform(-89.5, 89.5, n)
    lons = rng.uniform(-180.0, 180.0, n)
    ds = xr.Dataset(
        {"latixy": (("gridcell",), lats, {"units": "degrees_north"}),
         "longxy": (("gridcell",), lons, {"units": "degrees_east"})},
        attrs={"source": "E3SM ELM"})
    p = tmp_path / "elm_mesh.nc"
    ds.to_netcdf(p)
    return p


def test_peek_grid_kind_detects_elm(tmp_path: Path):
    mesh = _elm_mesh(tmp_path)
    assert _peek_grid_kind(str(mesh)) == "elm"


def test_render_elm_scatter_produces_png(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mesh = _elm_mesh(tmp_path, n=60)
    values = np.linspace(0.0, 1.0, 60)
    env = render_map({
        "values": values.tolist(),
        "mesh_path": str(mesh),
        "title": "ELM scatter test",
    })
    assert env["ok"] is True, env.get("error")
    out_path = Path(env["result"]["output_path"])
    assert out_path.exists()
    assert out_path.stat().st_size > 5_000
    # Oracle should record the gridcell kind label.
    assert env["result"]["oracle"]["drawn"]["grid_kind"] == \
        "unstructured_elm"
    assert env["result"]["oracle"]["drawn"]["n_cells"] == 60


def test_render_elm_shape_mismatch(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    mesh = _elm_mesh(tmp_path, n=60)
    # Wrong-size values
    env = render_map({
        "values": [0.0] * 30,
        "mesh_path": str(mesh),
    })
    assert env["ok"] is False
    assert env["error"]["code"] == "shape_mismatch"

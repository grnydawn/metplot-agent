"""Cycle 11 task 3 — MCP server dispatch for the new cell helpers."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.server import dispatch, list_tool_names


def _mesh(tmp_path: Path, n_cells: int = 8) -> Path:
    rng = np.random.default_rng(0)
    ds = xr.Dataset(
        {
            "latCell": (("nCells",),
                        rng.uniform(-np.pi / 2, np.pi / 2, n_cells)),
            "lonCell": (("nCells",),
                        rng.uniform(0, 2 * np.pi, n_cells)),
        },
        attrs={"Conventions": "MPAS"},
    )
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)
    return p


def test_list_tool_names_includes_new_helpers():
    names = list_tool_names()
    assert "find_nearest_cell" in names
    assert "cells_in_bbox" in names


def test_dispatch_find_nearest_cell(tmp_path: Path):
    p = _mesh(tmp_path, n_cells=8)
    env = dispatch("find_nearest_cell",
                    {"mesh_path": str(p), "lat": 0.0, "lon": 0.0})
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    assert isinstance(r["cell_index"], int)
    assert 0 <= r["cell_index"] < 8
    assert "actual_lat" in r and "actual_lon" in r


def test_dispatch_cells_in_bbox(tmp_path: Path):
    p = _mesh(tmp_path, n_cells=8)
    env = dispatch("cells_in_bbox", {
        "mesh_path": str(p),
        "lat_min": -90.0, "lat_max": 90.0,
        "lon_min": 0.0, "lon_max": 360.0,
    })
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # Every cell should be in the global bbox.
    assert r["n_cells_in_bbox"] == 8
    assert r["n_cells_total"] == 8


def test_dispatch_find_nearest_cell_missing_mesh(tmp_path: Path):
    env = dispatch("find_nearest_cell",
                    {"mesh_path": str(tmp_path / "nope.nc"),
                     "lat": 0.0, "lon": 0.0})
    assert env["ok"] is False
    assert env["error"]["code"] == "file_not_found"


def test_dispatch_bad_args_returns_internal_error(tmp_path: Path):
    p = _mesh(tmp_path)
    env = dispatch("find_nearest_cell",
                    {"mesh_path": str(p), "lat": 0.0})  # missing lon
    assert env["ok"] is False
    assert env["error"]["code"] == "internal_error"

"""Cycle 11 task 2 — read_slice cell-index plumbing.

read_slice(..., cell_index=N) and read_slice(..., cell_indices=[...])
reduce a slice along the unstructured cell axis. Case-insensitive
on the dim name (NCells/nCells/ncells). Mutually exclusive with
lat/lon selectors.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice


def _omega_history(tmp_path: Path, n_cells: int = 12, n_layers: int = 4,
                    n_time: int = 1) -> Path:
    """Synthetic MPAS history (uppercase NCells, no mesh inside)."""
    rng = np.random.default_rng(0)
    ds = xr.Dataset(
        {
            "Temperature": (
                ("time", "NCells", "NVertLayers"),
                rng.uniform(-2, 30, (n_time, n_cells, n_layers)),
                {"units": "degree_C"},
            ),
            "SshCell": (
                ("time", "NCells"),
                rng.uniform(-1, 1, (n_time, n_cells)),
                {"units": "m"},
            ),
        },
        attrs={"source": "MPAS", "core_name": "ocean"},
    )
    p = tmp_path / "hist.nc"
    ds.to_netcdf(p)
    return p


def _omega_mesh(tmp_path: Path, n_cells: int = 12) -> Path:
    """Synthetic MPAS mesh (lowercase nCells)."""
    rng = np.random.default_rng(1)
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


def test_cell_index_single_reduces_to_zero_d_cell_axis(tmp_path: Path):
    """cell_index=N → variable's NCells dim is reduced (isel that
    cell). Result for Temperature[t=first, level=0, cell=N] should
    be a scalar."""
    hist = _omega_history(tmp_path)
    mesh = _omega_mesh(tmp_path)
    env = read_slice(
        str(hist), variable="Temperature", time="first", level=0,
        cell_index=3, mesh_path=str(mesh), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # All three axis reductions: shape is empty (scalar).
    assert r["shape"] == [], r["shape"]


def test_cell_index_single_keeps_vertical_axis(tmp_path: Path):
    """cell_index=N + time=first (no level) → leaves the vertical
    axis intact, ready for a profile render. Shape = [NVertLayers]."""
    hist = _omega_history(tmp_path)
    mesh = _omega_mesh(tmp_path)
    env = read_slice(
        str(hist), variable="Temperature", time="first",
        cell_index=3, mesh_path=str(mesh), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [4]


def test_cell_indices_subset_keeps_cell_axis(tmp_path: Path):
    """cell_indices=[1, 5, 7] → variable's NCells dim reduced to
    those 3 cells (not removed)."""
    hist = _omega_history(tmp_path)
    mesh = _omega_mesh(tmp_path)
    env = read_slice(
        str(hist), variable="SshCell", time="first",
        cell_indices=[1, 5, 7], mesh_path=str(mesh),
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [3]


def test_cell_index_case_insensitive_on_dim_name(tmp_path: Path):
    """Real Omega history uses uppercase NCells; the cell-index
    isel must match it case-insensitively."""
    hist = _omega_history(tmp_path)   # ships uppercase NCells
    mesh = _omega_mesh(tmp_path)      # ships lowercase nCells
    env = read_slice(
        str(hist), variable="SshCell", time="first",
        cell_index=2, mesh_path=str(mesh), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == []


def test_cell_index_mutually_exclusive_with_lat(tmp_path: Path):
    """Passing both cell_index and lat is a spec error."""
    hist = _omega_history(tmp_path)
    mesh = _omega_mesh(tmp_path)
    env = read_slice(
        str(hist), variable="Temperature", time="first",
        cell_index=3, lat=40.0, mesh_path=str(mesh),
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]


def test_cell_index_out_of_range_errors(tmp_path: Path):
    """cell_index larger than NCells must return a structured
    error, not raise."""
    hist = _omega_history(tmp_path, n_cells=12)
    mesh = _omega_mesh(tmp_path, n_cells=12)
    env = read_slice(
        str(hist), variable="Temperature", time="first", level=0,
        cell_index=99, mesh_path=str(mesh),
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "out_of_bounds", "internal_error"), env["error"]["code"]


def test_cell_index_without_mesh_path_works(tmp_path: Path):
    """mesh_path is OPTIONAL for cell_index — the selector only
    needs the variable's cell axis, not the mesh geometry. (Useful
    when you already have the cell index from a separate query.)"""
    hist = _omega_history(tmp_path)
    env = read_slice(
        str(hist), variable="SshCell", time="first",
        cell_index=2, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == []

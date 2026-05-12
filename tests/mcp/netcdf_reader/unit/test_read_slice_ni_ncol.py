"""Cycle 13 theme A — read_slice cell_index on ni / ncol dims.

Cycle 11 shipped cell_index for MPAS's NCells dim only. Cycle 13
extends it to CICE (`ni`) and EAMxx (`ncol`). The dim-name
matching is case-insensitive against `{ncells, ni, ncol}`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice


def _cice_history(tmp_path: Path, n_cells: int = 16,
                   n_cat: int = 2) -> Path:
    """Synthetic CICE history shape (ncat, ni)."""
    rng = np.random.default_rng(0)
    ds = xr.Dataset(
        {"aicen": (("ncat", "ni"),
                    rng.uniform(0, 1, (n_cat, n_cells)),
                    {"units": "1"})},
        attrs={"source": "CICE"})
    p = tmp_path / "cice_hist.nc"
    ds.to_netcdf(p)
    return p


def _eamxx_history(tmp_path: Path, n_cols: int = 32,
                    n_lev: int = 8, n_time: int = 1) -> Path:
    """Synthetic EAMxx physics history (time, ncol, lev)."""
    rng = np.random.default_rng(1)
    ds = xr.Dataset(
        {"T_mid": (("time", "ncol", "lev"),
                    rng.uniform(200, 300,
                                 (n_time, n_cols, n_lev)),
                    {"units": "K"})},
        coords={"time": np.array([0], dtype="int64")},
        attrs={"source": "SCREAM"})
    p = tmp_path / "eamxx_hist.nc"
    ds.to_netcdf(p)
    return p


def test_cell_index_on_ni_dim_cice(tmp_path: Path):
    """CICE history: read_slice(..., cell_index=3) reduces the `ni`
    dim to a single cell."""
    p = _cice_history(tmp_path)
    env = read_slice(str(p), variable="aicen", cell_index=3,
                     adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # ncat=2 stays; ni dim removed (scalar isel)
    assert env["result"]["shape"] == [2]


def test_cell_indices_on_ni_dim_cice(tmp_path: Path):
    """CICE history with subset of ni cells."""
    p = _cice_history(tmp_path, n_cells=16)
    env = read_slice(str(p), variable="aicen",
                     cell_indices=[1, 5, 9], adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [2, 3]  # (ncat, len(indices))


def test_cell_index_on_ncol_dim_eamxx(tmp_path: Path):
    """EAMxx history: read_slice(..., cell_index=10) reduces ncol."""
    p = _eamxx_history(tmp_path)
    env = read_slice(str(p), variable="T_mid", time="first",
                     cell_index=10, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # time + ncol both scalar-iseled → only lev remains
    assert env["result"]["shape"] == [8]


def test_cell_indices_on_ncol_dim_eamxx(tmp_path: Path):
    """EAMxx history with subset of ncol cells."""
    p = _eamxx_history(tmp_path, n_cols=20)
    env = read_slice(str(p), variable="T_mid", time="first",
                     cell_indices=[2, 7, 13], adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # time scalar-iseled → (ncol_subset=3, lev=8)
    assert env["result"]["shape"] == [3, 8]


def test_out_of_range_on_ni(tmp_path: Path):
    """cell_index >= ni size → out_of_bounds."""
    p = _cice_history(tmp_path, n_cells=16)
    env = read_slice(str(p), variable="aicen", cell_index=99,
                     adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "out_of_bounds", "internal_error"), env["error"]["code"]


def test_out_of_range_on_ncol(tmp_path: Path):
    p = _eamxx_history(tmp_path, n_cols=32)
    env = read_slice(str(p), variable="T_mid", time="first",
                     cell_index=999, adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "out_of_bounds", "internal_error"), env["error"]["code"]

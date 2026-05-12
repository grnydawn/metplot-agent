"""Cycle 9 task 8 — vertical-dim recognition extended for CICE +
EAMxx.

resolve_spec must recognize new vertical-dim names so that
`level=...` selectors work on CICE history (nilyr / nslyr / nkice
/ nkbio / ncat / ntilyr / ntslyr) and EAMxx physics (ilev as well
as the already-recognized lev).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def _cice_history_with_layers(tmp_path: Path) -> Path:
    """CICE-shaped fixture: variable on (ncat, nilyr, nj, ni)."""
    ds = xr.Dataset(
        {
            "eicen": (
                ("ncat", "nilyr", "nj", "ni"),
                np.zeros((1, 4, 1, 6)),
                {"long_name": "ice enthalpy"},
            ),
            "aicen": (
                ("ncat", "nj", "ni"),
                np.zeros((1, 1, 6)),
            ),
            "vicen": (
                ("ncat", "nj", "ni"),
                np.zeros((1, 1, 6)),
            ),
            "Tsfcn": (
                ("ncat", "nj", "ni"),
                np.zeros((1, 1, 6)),
            ),
        }
    )
    p = tmp_path / "cice.r.nc"
    ds.to_netcdf(p)
    return p


def _eamxx_history_with_ilev(tmp_path: Path) -> Path:
    """EAMxx-shaped fixture: variable on (time, ncol, ilev) interface
    levels."""
    ds = xr.Dataset(
        {
            "w_int": (
                ("time", "ncol", "ilev"),
                np.zeros((1, 6, 9)),
                {"units": "m/s"},
            ),
            "T_mid": (
                ("time", "ncol", "lev"),
                np.zeros((1, 6, 8)),
            ),
            "ps": (
                ("time", "ncol"),
                np.zeros((1, 6)),
            ),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
        },
    )
    p = tmp_path / "eamxx.h.nc"
    ds.to_netcdf(p)
    return p


def test_cice_nilyr_is_recognized_as_vertical(tmp_path):
    """level=0 on a CICE var with `nilyr` axis must resolve cleanly,
    not fail with not_4d."""
    p = _cice_history_with_layers(tmp_path)
    env = resolve_spec(
        str(p), variable="eicen", level=0, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["resolved"]["level_index"] == 0


def test_cice_ncat_is_recognized_as_vertical(tmp_path):
    """ncat (thickness category axis) must also be recognizable as a
    "level" — it's the natural reducible dim for CICE per-cat fields."""
    p = _cice_history_with_layers(tmp_path)
    env = resolve_spec(
        str(p), variable="aicen", level=0, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["resolved"]["level_index"] == 0


def test_eamxx_ilev_is_recognized_as_vertical(tmp_path):
    """EAMxx interface-level dim (ilev) must be recognized; without
    this, plotting any interface-level var fails not_4d."""
    p = _eamxx_history_with_ilev(tmp_path)
    env = resolve_spec(
        str(p), variable="w_int", level=0, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["resolved"]["level_index"] == 0


def test_eamxx_lev_still_recognized(tmp_path):
    """Regression: the pre-existing `lev` name must keep working."""
    p = _eamxx_history_with_ilev(tmp_path)
    env = resolve_spec(
        str(p), variable="T_mid", level=0, adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["resolved"]["level_index"] == 0

"""Cycle 9 task 7 — inspect() EAMxx history + physics-grid pairing.

EAMxx history files declare CF-1.x but ship no lat/lon in-file;
geometry comes from a separate scrip-style grid file. Also: EAMxx
output may include dycore-axis variables (elem×gp×gp) that aren't
plottable in cycle 9 — those should be flagged with a structured
DYCORE_VARS_PRESENT warning, not error out the inspect.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def _eamxx_history_physics_only(ncol: int = 16) -> xr.Dataset:
    """EAMxx history with only physics-axis variables."""
    return xr.Dataset(
        {
            "T_mid": (
                ("time", "ncol", "lev"),
                np.zeros((1, ncol, 8)),
                {"standard_name": "air_temperature", "units": "K"},
            ),
            "ps": (
                ("time", "ncol"),
                np.zeros((1, ncol)),
                {"standard_name": "surface_air_pressure", "units": "Pa"},
            ),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
        },
    )


def _eamxx_history_dual_grid(ncol: int = 16, elem: int = 4) -> xr.Dataset:
    """EAMxx history with physics + dycore variables (typical
    SCREAM restart shape).

    Note: xarray emits a UserWarning when the same dim name appears
    multiple times in a tuple (gp×gp); we use distinct names
    `gp1`/`gp2` here so the file constructs cleanly, but downstream
    detection in inspect.py only looks for any var whose dim list
    contains both `elem` and `gp` — to exercise that, we add one
    variable that uses a single 'gp' dim alongside 'elem' (real
    EAMxx files have gp×gp; our detector treats the presence of
    'elem' + 'gp' together as the dycore signal regardless of
    duplication).
    """
    ds = xr.Dataset(
        {
            "T_mid": (
                ("time", "ncol", "lev"),
                np.zeros((1, ncol, 8)),
                {"standard_name": "air_temperature", "units": "K"},
            ),
            "v_dyn": (
                ("time", "elem", "gp", "lev"),
                np.zeros((1, elem, 4, 8)),
            ),
            "ps_dyn": (
                ("time", "elem", "gp"),
                np.zeros((1, elem, 4)),
            ),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
        },
    )
    return ds


def _eamxx_phys_grid(ncol: int = 16) -> xr.Dataset:
    """Synthetic SCRIP-style EAMxx physics grid file."""
    rng = np.random.default_rng(0)
    lat = rng.uniform(-90.0, 90.0, size=ncol)
    lon = rng.uniform(0.0, 360.0, size=ncol)
    return xr.Dataset(
        {
            "lat": (("ncol",), lat),
            "lon": (("ncol",), lon),
        }
    )


class TestInspectBareEAMxx:
    def test_returns_ambiguous_mesh_pairing_required(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _eamxx_history_physics_only().to_netcdf(tmp_path / "eamxx.nc")
        env = inspect(str(tmp_path / "eamxx.nc"), adapter=NetCDFAdapter())
        assert env["ok"] is False
        assert env["error"]["subcode"] == "mesh_pairing_required"
        assert env["error"]["context"]["family"] == "EAMxx"
        assert env["error"]["context"]["missing_coords"] == ["lat", "lon"]


class TestInspectPairedEAMxx:
    def test_returns_ok_combined_envelope(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _eamxx_history_physics_only().to_netcdf(tmp_path / "eamxx.nc")
        _eamxx_phys_grid().to_netcdf(tmp_path / "ne16pg2_scrip.nc")
        env = inspect(
            str(tmp_path / "eamxx.nc"),
            mesh_path=str(tmp_path / "ne16pg2_scrip.nc"),
            adapter=NetCDFAdapter())
        assert env["ok"] is True, env.get("error")
        spatial = env["result"]["spatial"]
        assert spatial is not None
        assert spatial["coord_kind"] == "unstructured"
        assert spatial["cell_dim"] == "ncol"
        assert spatial["n_cells"] == 16

    def test_tags_physics_variables_cell_centered(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _eamxx_history_physics_only().to_netcdf(tmp_path / "eamxx.nc")
        _eamxx_phys_grid().to_netcdf(tmp_path / "ne16pg2_scrip.nc")
        env = inspect(
            str(tmp_path / "eamxx.nc"),
            mesh_path=str(tmp_path / "ne16pg2_scrip.nc"),
            adapter=NetCDFAdapter())
        kinds = {v["name"]: v.get("grid_kind")
                 for v in env["result"]["variables"]}
        assert kinds["T_mid"] == "cell_centered", kinds
        assert kinds["ps"] == "cell_centered", kinds

    def test_dycore_vars_present_warning_and_tagging(
            self, tmp_path: Path, monkeypatch) -> None:
        """Dual-grid EAMxx file: physics vars tagged cell_centered,
        dycore vars tagged dycore_spectral, and a structured warning
        emitted."""
        monkeypatch.chdir(tmp_path)
        _eamxx_history_dual_grid().to_netcdf(tmp_path / "eamxx.nc")
        _eamxx_phys_grid().to_netcdf(tmp_path / "ne16pg2_scrip.nc")
        env = inspect(
            str(tmp_path / "eamxx.nc"),
            mesh_path=str(tmp_path / "ne16pg2_scrip.nc"),
            adapter=NetCDFAdapter())
        assert env["ok"] is True, env.get("error")
        # Structured warning emitted with the dycore var list.
        warn_codes = [w["code"] for w in env["warnings"]]
        assert "dycore_vars_present" in warn_codes, env["warnings"]
        # Tagging splits cleanly: physics vs dycore.
        kinds = {v["name"]: v.get("grid_kind")
                 for v in env["result"]["variables"]}
        assert kinds["T_mid"] == "cell_centered", kinds
        assert kinds["v_dyn"] == "dycore_spectral", kinds
        assert kinds["ps_dyn"] == "dycore_spectral", kinds

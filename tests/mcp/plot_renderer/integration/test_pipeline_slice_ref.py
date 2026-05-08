# tests/mcp/plot_renderer/integration/test_pipeline_slice_ref.py
"""End-to-end slice_ref form pipeline.

The slice file format is the cross-MCP contract; if cycle-1 changes
how it writes slice files, this test catches the drift.
"""
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.tools import render_map as rm


def _write_cf_slice(path: Path, *, curvilinear: bool = False) -> None:
    if not curvilinear:
        lat = np.linspace(-30, 30, 8).astype("f4")
        lon = np.linspace(-60, 60, 12).astype("f4")
        values = np.outer(np.cos(np.deg2rad(lat)),
                           np.sin(np.deg2rad(lon))).astype("f4")
        ds = xr.Dataset(
            {"tos": (("lat", "lon"), values,
                     {"units": "K", "long_name": "sea surface temperature",
                      "standard_name": "sea_surface_temperature"})},
            coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                    "lon": ("lon", lon, {"units": "degrees_east"})},
            attrs={"Conventions": "CF-1.7"},
        )
    else:
        # Mock WRF-style 2D coords (curvilinear)
        ny, nx = 6, 9
        xlat = np.tile(np.linspace(-30, 30, ny).reshape(ny, 1), (1, nx))
        xlon = np.tile(np.linspace(-60, 60, nx).reshape(1, nx), (ny, 1))
        values = np.cos(np.deg2rad(xlat)) * np.sin(np.deg2rad(xlon))
        values = values.astype("f4")
        ds = xr.Dataset(
            {"tos": (("y", "x"), values, {"units": "K"})},
            coords={"xlat": (("y", "x"), xlat),
                    "xlon": (("y", "x"), xlon),
                    "y": np.arange(ny),
                    "x": np.arange(nx)},
            attrs={"Conventions": "CF-1.7"},
        )
    ds.to_netcdf(path, engine="netcdf4")


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_rectilinear_slice_ref_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "slice.nc"
    _write_cf_slice(p, curvilinear=False)
    spec = {"slice_ref": {"path": str(p), "format": "netcdf",
                            "variable": "tos"},
            "output_path": str(tmp_path / "from_slice.png"),
            "title": "from slice"}
    env = rm.render_map(spec)
    assert env["ok"] is True, env.get("error")
    assert (tmp_path / "from_slice.png").exists()


def test_missing_variable_returns_invalid_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "slice.nc"
    _write_cf_slice(p)
    spec = {"slice_ref": {"path": str(p), "format": "netcdf",
                            "variable": "does_not_exist"}}
    if rm._CARTOPY_OK:
        env = rm.render_map(spec)
        assert env["ok"] is False
        assert env["error"]["code"] == "invalid_spec"


def test_nonexistent_slice_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"slice_ref": {"path": str(tmp_path / "no.nc"),
                            "format": "netcdf", "variable": "tos"}}
    if rm._CARTOPY_OK:
        env = rm.render_map(spec)
        assert env["ok"] is False
        assert env["error"]["code"] == "invalid_spec"

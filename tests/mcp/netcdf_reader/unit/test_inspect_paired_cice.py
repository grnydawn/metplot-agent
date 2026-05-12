"""Cycle 9 task 7 — inspect() CICE history + grid pairing.

Mirrors test_inspect_paired.py for the CICE flow:
- bare CICE restart → ambiguous mesh_pairing_required, family=CICE
- paired call (history + grid) → combined envelope, spatial from
  grid, variables tagged cell_centered.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def _cice_history_flattened(n_cells: int = 24) -> xr.Dataset:
    """Synthetic CICE restart — flattened (nj=1, ni=N) shape."""
    return xr.Dataset(
        {
            "aicen": (("ncat", "nj", "ni"),
                      np.zeros((1, 1, n_cells), dtype=np.float64)),
            "vicen": (("ncat", "nj", "ni"),
                      np.zeros((1, 1, n_cells), dtype=np.float64)),
            "Tsfcn": (("ncat", "nj", "ni"),
                      np.zeros((1, 1, n_cells), dtype=np.float64)),
            "uvel": (("nj", "ni"),
                     np.zeros((1, n_cells), dtype=np.float64)),
            "iceumask": (("nj", "ni"),
                         np.zeros((1, n_cells), dtype=np.float64)),
            "stressp_1": (("nj", "ni"),
                          np.zeros((1, n_cells), dtype=np.float64)),
        },
    )


def _cice_grid(nj: int = 4, ni: int = 6) -> xr.Dataset:
    lat_1d = np.linspace(-80.0, 80.0, nj)
    lon_1d = np.linspace(0.0, 350.0, ni)
    return xr.Dataset(
        {
            "TLAT": (("nj", "ni"),
                     np.broadcast_to(lat_1d[:, None],
                                     (nj, ni)).copy()),
            "TLON": (("nj", "ni"),
                     np.broadcast_to(lon_1d[None, :],
                                     (nj, ni)).copy()),
        },
    )


class TestInspectBareCICE:
    def test_returns_ambiguous_mesh_pairing_required(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _cice_history_flattened().to_netcdf(tmp_path / "cice.r.nc")
        env = inspect(str(tmp_path / "cice.r.nc"), adapter=NetCDFAdapter())
        assert env["ok"] is False
        assert env["error"]["code"] == "ambiguous"
        assert env["error"]["subcode"] == "mesh_pairing_required"
        assert env["error"]["retry_with_param"] == "mesh_path"
        # Family label drives the prompt wording.
        assert env["error"]["context"]["family"] == "CICE"
        assert env["error"]["context"]["missing_coords"] == ["TLAT", "TLON"]

    def test_surfaces_sibling_grid_as_candidate(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _cice_history_flattened().to_netcdf(tmp_path / "cice.r.nc")
        # Drop a sibling grid file so the candidate scan finds it.
        _cice_grid().to_netcdf(tmp_path / "grid.nc")
        env = inspect(str(tmp_path / "cice.r.nc"), adapter=NetCDFAdapter())
        cand_labels = [c["label"] for c in env["error"]["candidates"]]
        assert "grid.nc" in cand_labels, cand_labels


class TestInspectPairedCICE:
    def test_returns_ok_combined_envelope(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _cice_history_flattened().to_netcdf(tmp_path / "cice.r.nc")
        _cice_grid().to_netcdf(tmp_path / "grid.nc")
        env = inspect(
            str(tmp_path / "cice.r.nc"),
            mesh_path=str(tmp_path / "grid.nc"),
            adapter=NetCDFAdapter())
        assert env["ok"] is True, env.get("error")
        spatial = env["result"]["spatial"]
        assert spatial is not None
        assert spatial["coord_kind"] == "unstructured"
        assert spatial["cell_dim"] == "ni"
        assert spatial["n_cells"] == 24
        assert spatial["lat_var"] == "TLAT"

    def test_tags_cell_centered_variables(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _cice_history_flattened().to_netcdf(tmp_path / "cice.r.nc")
        _cice_grid().to_netcdf(tmp_path / "grid.nc")
        env = inspect(
            str(tmp_path / "cice.r.nc"),
            mesh_path=str(tmp_path / "grid.nc"),
            adapter=NetCDFAdapter())
        kinds = {v["name"]: v.get("grid_kind")
                 for v in env["result"]["variables"]}
        # Every CICE var lives on (nj, ni); tag must fire on all.
        assert kinds["aicen"] == "cell_centered", kinds
        assert kinds["Tsfcn"] == "cell_centered", kinds
        assert kinds["uvel"] == "cell_centered", kinds

    def test_pair_with_size_mismatch_errors(
            self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _cice_history_flattened(n_cells=24).to_netcdf(tmp_path / "cice.r.nc")
        _cice_grid(nj=4, ni=8).to_netcdf(tmp_path / "grid.nc")  # 32 ≠ 24
        env = inspect(
            str(tmp_path / "cice.r.nc"),
            mesh_path=str(tmp_path / "grid.nc"),
            adapter=NetCDFAdapter())
        assert env["ok"] is False
        assert env["error"]["code"] == "multi_file_combine_failed"
        assert "mismatch" in env["error"]["message"].lower()

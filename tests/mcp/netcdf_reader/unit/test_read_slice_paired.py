"""Cycle 8 Phase B task 4 — thread mesh_path through resolve_spec
+ read_slice so the renderer (task 5) can pick up the pair.

read_slice doesn't attach lat/lon coords to its output (the
NCells dim has no meaningful 1-D coord — it's just an index).
Instead it echoes `mesh_path` in the result so the renderer
can open the mesh itself.

Cycle-8 spec §3.3 names both files."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def _mpas_history(n_cells: int = 12) -> xr.Dataset:
    rng = np.random.default_rng(0)
    return xr.Dataset(
        {
            "Temperature": (
                ("time", "NCells", "NVertLayers"),
                rng.uniform(-2, 30, (1, n_cells, 4)),
                {"units": "C"},
            ),
        },
        attrs={"source": "MPAS", "core_name": "ocean",
               "model_name": "mpas"},
    )


def _mpas_mesh(n_cells: int = 12) -> xr.Dataset:
    rng = np.random.default_rng(1)
    return xr.Dataset(
        {
            "latCell": (("nCells",),
                        rng.uniform(-np.pi / 2, np.pi / 2, n_cells)),
            "lonCell": (("nCells",),
                        rng.uniform(0, 2 * np.pi, n_cells)),
        },
        attrs={"Conventions": "MPAS"},
    )


class TestResolveSpecWithMeshPath:
    def test_accepts_mesh_path_for_mpas_pair(self, tmp_path: Path,
                                              monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _mpas_history().to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh().to_netcdf(tmp_path / "mesh.nc")
        env = resolve_spec(
            str(tmp_path / "hist.nc"), "Temperature",
            time="first", level=0,
            mesh_path=str(tmp_path / "mesh.nc"),
            adapter=NetCDFAdapter(),
        )
        assert env["ok"] is True, env.get("error")

    def test_refuses_pair_on_dim_mismatch(self, tmp_path: Path,
                                            monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _mpas_history(n_cells=12).to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh(n_cells=5).to_netcdf(tmp_path / "mesh.nc")
        env = resolve_spec(
            str(tmp_path / "hist.nc"), "Temperature",
            time="first", level=0,
            mesh_path=str(tmp_path / "mesh.nc"),
            adapter=NetCDFAdapter(),
        )
        assert env["ok"] is False
        msg = env["error"]["message"].lower()
        assert "mismatch" in msg or "dim" in msg

    def test_mesh_path_defaults_to_none(self, tmp_path: Path,
                                          monkeypatch,
                                          cf_3d_file) -> None:
        """Existing non-paired callers must not regress."""
        env = resolve_spec(
            str(cf_3d_file), "tos", time="first",
            adapter=NetCDFAdapter(),
        )
        assert "ok" in env


class TestReadSliceWithMeshPath:
    def test_accepts_mesh_path_for_mpas_pair(self, tmp_path: Path,
                                               monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _mpas_history().to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh().to_netcdf(tmp_path / "mesh.nc")
        env = read_slice(
            str(tmp_path / "hist.nc"), "Temperature",
            time="first", level=0,
            mesh_path=str(tmp_path / "mesh.nc"),
            adapter=NetCDFAdapter(),
        )
        assert env["ok"] is True, env.get("error")
        # 1-D field after time + level selection
        assert env["result"]["dims"] == ["NCells"]
        assert env["result"]["shape"] == [12]

    def test_echoes_mesh_path_in_result(self, tmp_path: Path,
                                          monkeypatch) -> None:
        """The slice output advertises which mesh file was paired so
        the renderer can open it. Echoed at the top level of result."""
        monkeypatch.chdir(tmp_path)
        _mpas_history().to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh().to_netcdf(tmp_path / "mesh.nc")
        env = read_slice(
            str(tmp_path / "hist.nc"), "Temperature",
            time="first", level=0,
            mesh_path=str(tmp_path / "mesh.nc"),
            adapter=NetCDFAdapter(),
        )
        assert env["result"]["mesh_path"].endswith("mesh.nc")

    def test_refuses_on_dim_mismatch(self, tmp_path: Path,
                                       monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        _mpas_history(n_cells=12).to_netcdf(tmp_path / "hist.nc")
        _mpas_mesh(n_cells=5).to_netcdf(tmp_path / "mesh.nc")
        env = read_slice(
            str(tmp_path / "hist.nc"), "Temperature",
            time="first", level=0,
            mesh_path=str(tmp_path / "mesh.nc"),
            adapter=NetCDFAdapter(),
        )
        assert env["ok"] is False

    def test_mesh_path_defaults_to_none(self, tmp_path: Path,
                                         monkeypatch,
                                         cf_3d_file) -> None:
        """Existing rectilinear path must not regress when no
        mesh_path is supplied. cf_3d_file's variable is `tos`
        on (time, lat, lon) — no level dim."""
        env = read_slice(
            str(cf_3d_file), "tos", time="first",
            adapter=NetCDFAdapter(),
        )
        assert env["ok"] is True

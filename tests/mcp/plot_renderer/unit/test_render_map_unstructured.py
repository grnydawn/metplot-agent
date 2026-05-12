"""Cycle 8 Phase B task 5 — unstructured-map renderer branch.

render_map accepts an MPAS-shape spec — 1-D NCells field values
plus `mesh_path` — and produces a recognizable global map. Cycle-8
spec §1 success criterion #4 + §3.4.

Renders via uxarray's `uxgrid.to_polycollection()` (Phase A primary
path, with the documented workaround for the
`UxDataArray.to_polycollection(cache=False)` bug in
uxarray v2026.04.1)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.tools.render_map import render_map


def _mpas_mesh(tmp_path: Path, n_cells: int = 12) -> Path:
    """Synthetic MPAS mesh-style file. Uses radians per Phase A
    finding #1 to exercise the conversion path end-to-end.
    Includes the connectivity tables uxarray needs to construct
    primal + dual meshes (verticesOnCell, cellsOnVertex)."""
    rng = np.random.default_rng(0)
    n_vert = 20
    ds = xr.Dataset(
        {
            "latCell": (("nCells",),
                        rng.uniform(-np.pi / 2, np.pi / 2, n_cells)),
            "lonCell": (("nCells",),
                        rng.uniform(0, 2 * np.pi, n_cells)),
            "latVertex": (("nVertices",),
                          rng.uniform(-np.pi / 2, np.pi / 2, n_vert)),
            "lonVertex": (("nVertices",),
                          rng.uniform(0, 2 * np.pi, n_vert)),
            "verticesOnCell": (("nCells", "maxEdges"),
                               rng.integers(1, n_vert + 1,
                                             (n_cells, 6))),
            "cellsOnVertex": (("nVertices", "vertexDegree"),
                               rng.integers(1, n_cells + 1,
                                             (n_vert, 3))),
            "nEdgesOnCell": (("nCells",), np.full(n_cells, 6)),
        },
        attrs={"Conventions": "MPAS", "core_name": "ocean"},
    )
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)
    return p


def _make_spec(tmp_path: Path, values: np.ndarray, mesh_path: Path,
                **overrides) -> dict:
    return {
        "values": values.tolist(),
        "mesh_path": str(mesh_path),
        "output_path": str(tmp_path / "out.png"),
        "title": "MPAS-Ocean Temperature (test)",
        "colormap": "viridis",
        "projection": "Robinson",
        **overrides,
    }


@pytest.fixture
def uxarray_or_skip():
    """Skip the test cleanly if uxarray isn't installed. Required
    by `[cycle8-poc]` optional-deps group."""
    pytest.importorskip(
        "uxarray",
        reason=("uxarray not installed; install via "
                "`uv pip install -e '.[cycle8-poc]'`"))


class TestRenderUnstructuredMap:
    def test_produces_png(self, tmp_path: Path,
                          uxarray_or_skip) -> None:
        mesh = _mpas_mesh(tmp_path)
        values = np.linspace(-2, 30, 12)
        env = render_map(_make_spec(tmp_path, values, mesh))
        assert env["ok"] is True, env.get("error")
        out_path = Path(env["result"]["output_path"])
        assert out_path.is_file()
        assert out_path.suffix == ".png"
        assert out_path.stat().st_size > 10_000, (
            f"PNG suspiciously small ({out_path.stat().st_size} B); "
            f"likely an empty render")

    def test_oracle_records_unstructured_path(
        self, tmp_path: Path, uxarray_or_skip,
    ) -> None:
        """The result envelope's oracle block records that this was
        rendered via the unstructured branch, so downstream tools
        can audit which path produced the figure."""
        mesh = _mpas_mesh(tmp_path)
        values = np.linspace(-2, 30, 12)
        env = render_map(_make_spec(tmp_path, values, mesh))
        # The oracle's "drawn" block carries the projection name and
        # other audit info. For unstructured we mark `grid_kind`.
        assert env["result"]["oracle"]["drawn"]["grid_kind"] == (
            "unstructured")

    def test_refuses_when_values_shape_mismatches_mesh(
        self, tmp_path: Path, uxarray_or_skip,
    ) -> None:
        mesh = _mpas_mesh(tmp_path, n_cells=12)
        # Pass 5 values when the mesh has 12 cells
        values = np.linspace(-2, 30, 5)
        env = render_map(_make_spec(tmp_path, values, mesh))
        assert env["ok"] is False
        assert env["error"]["code"] == "shape_mismatch"
        msg = env["error"]["message"].lower()
        assert "length" in msg or "n_face" in msg or "shape" in msg

    def test_refuses_when_mesh_path_missing(
        self, tmp_path: Path, uxarray_or_skip,
    ) -> None:
        values = np.linspace(-2, 30, 12)
        spec = {
            "values": values.tolist(),
            "mesh_path": str(tmp_path / "no-such-mesh.nc"),
            "output_path": str(tmp_path / "out.png"),
        }
        env = render_map(spec)
        assert env["ok"] is False

    def test_rectilinear_path_still_works(
        self, tmp_path: Path,
    ) -> None:
        """Sanity: spec without mesh_path uses the existing
        rectilinear pcolormesh path. No regression."""
        lat = np.linspace(-90, 90, 19)
        lon = np.linspace(0, 357.5, 36)
        values = np.random.default_rng(0).normal(290, 5, (19, 36))
        env = render_map({
            "values": values.tolist(),
            "lat": lat.tolist(),
            "lon": lon.tolist(),
            "output_path": str(tmp_path / "rect-out.png"),
            "title": "Rectilinear sanity",
            "colormap": "viridis",
        })
        assert env["ok"] is True, env.get("error")
        # The rectilinear oracle path doesn't tag grid_kind; the
        # unstructured one does (test_oracle_records_unstructured_path
        # locks that in). Just confirm we got a PNG.
        out_path = Path(env["result"]["output_path"])
        assert out_path.is_file()

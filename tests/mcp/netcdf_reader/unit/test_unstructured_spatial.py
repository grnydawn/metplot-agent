"""Cycle 8 Phase B task 1 — extract_spatial for MPAS unstructured meshes.

The cycle-3 inspect envelope only knows `coord_kind in
{rectilinear, curvilinear}`. Cycle-6 Phase A dogfooding surfaced
that real MPAS-Ocean / Omega files are unstructured (Voronoi
mesh) and fail at the inspect → plot gate. This file locks in
the new `coord_kind: "unstructured"` shape introduced in cycle 8
Phase B §3.2.

Per Phase A library-survey finding #1, MPAS-Ocean files commonly
ship `latCell`/`lonCell` in **radians** with NO `units` attribute
(`lonCell` in [0, 2π], `latCell` in [-π/2, π/2]). The extractor
MUST detect by range and convert to degrees, or honor an explicit
`units="radians"` attr when present.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.conventions.mpas import extract_spatial_mpas
from src.mcp.netcdf_reader.tools.inspect import inspect


def _mpas_mesh_like_dataset(units: str | None = None,
                             radians: bool = True) -> xr.Dataset:
    """Synthetic MPAS-Ocean-mesh-shape Dataset.

    Cells: 12 points scattered across a globe.
    Vertices: 20 points (a typical 1.5-1.7 vertex-per-cell ratio).
    `verticesOnCell` connectivity is the canonical MPAS shape:
    1-indexed (0 = "no vertex" for cells with fewer than maxEdges sides).
    """
    rng = np.random.default_rng(0)
    n_cells, n_vert = 12, 20

    # Lat in [-π/2, π/2], lon in [0, 2π]. (Radians.)
    lat_cell = rng.uniform(-np.pi / 2, np.pi / 2, n_cells)
    lon_cell = rng.uniform(0, 2 * np.pi, n_cells)
    lat_vert = rng.uniform(-np.pi / 2, np.pi / 2, n_vert)
    lon_vert = rng.uniform(0, 2 * np.pi, n_vert)

    if not radians:
        lat_cell = np.degrees(lat_cell)
        lon_cell = np.degrees(lon_cell)
        lat_vert = np.degrees(lat_vert)
        lon_vert = np.degrees(lon_vert)

    voc = rng.integers(1, n_vert + 1, size=(n_cells, 6))  # 1-indexed
    n_edges_on_cell = np.full(n_cells, 6)

    attrs = {"units": units} if units else {}

    return xr.Dataset(
        {
            "latCell": (("nCells",), lat_cell, attrs),
            "lonCell": (("nCells",), lon_cell, attrs),
            "latVertex": (("nVertices",), lat_vert, attrs),
            "lonVertex": (("nVertices",), lon_vert, attrs),
            "verticesOnCell": (("nCells", "maxEdges"), voc),
            "nEdgesOnCell": (("nCells",), n_edges_on_cell),
        },
        attrs={
            "Conventions": "MPAS",
            "model_name": "mpas",
            "core_name": "ocean",
        },
    )


# ────────────────────────────────────────────────────────────────────
# Function-level tests on extract_spatial_mpas
# ────────────────────────────────────────────────────────────────────

class TestExtractSpatialMpas:
    def test_returns_unstructured_coord_kind(self):
        ds = _mpas_mesh_like_dataset()
        s = extract_spatial_mpas(ds)
        assert s is not None
        assert s["coord_kind"] == "unstructured", (
            f"expected coord_kind='unstructured'; got {s!r}")

    def test_returns_cell_dim_and_n_cells(self):
        ds = _mpas_mesh_like_dataset()
        s = extract_spatial_mpas(ds)
        assert s["cell_dim"] == "nCells"
        assert s["n_cells"] == 12

    def test_returns_lat_var_lon_var(self):
        ds = _mpas_mesh_like_dataset()
        s = extract_spatial_mpas(ds)
        assert s["lat_var"] == "latCell"
        assert s["lon_var"] == "lonCell"

    def test_returns_vertex_vars(self):
        """For polygon-fill rendering the renderer needs the vertex
        coord vars + the connectivity table."""
        ds = _mpas_mesh_like_dataset()
        s = extract_spatial_mpas(ds)
        assert s["vertex_lat_var"] == "latVertex"
        assert s["vertex_lon_var"] == "lonVertex"
        assert s["vertices_on_cell_var"] == "verticesOnCell"

    def test_converts_radians_to_degrees_when_no_units(self):
        """Phase A finding #1: MPAS-Ocean ships lat/lon in radians
        with units=None. Detect by range (|max| <= 2π+ε) and convert."""
        ds = _mpas_mesh_like_dataset(units=None, radians=True)
        s = extract_spatial_mpas(ds)
        # lat_range should fit inside [-90, 90] after conversion
        lo, hi = s["lat_range"]
        assert -90 <= lo <= 90, f"lat_range[0] = {lo} not in [-90, 90]"
        assert -90 <= hi <= 90, f"lat_range[1] = {hi} not in [-90, 90]"
        # lon_range should fit inside [0, 360]
        lo, hi = s["lon_range"]
        assert 0 <= lo <= 360, f"lon_range[0] = {lo} not in [0, 360]"
        assert 0 <= hi <= 360, f"lon_range[1] = {hi} not in [0, 360]"

    def test_converts_radians_to_degrees_with_explicit_units(self):
        """Some MPAS variants DO set units='radians'. Honor it."""
        ds = _mpas_mesh_like_dataset(units="radians", radians=True)
        s = extract_spatial_mpas(ds)
        lo, hi = s["lat_range"]
        assert -90 <= lo <= 90
        assert -90 <= hi <= 90

    def test_leaves_degrees_alone(self):
        """If the values are already in [-180, 180] / [-90, 90] degrees,
        no conversion."""
        ds = _mpas_mesh_like_dataset(units="degrees", radians=False)
        s = extract_spatial_mpas(ds)
        # Original lat range was [-π/2, π/2] * 180/π ≈ [-90, 90]; the
        # ranges should be in degrees already.
        lo, hi = s["lat_range"]
        assert -90 <= lo <= 90
        assert -90 <= hi <= 90

    def test_lon_convention_is_0_360_for_mpas(self):
        """MPAS-Ocean canonically stores lon in [0, 2π] = [0, 360]."""
        ds = _mpas_mesh_like_dataset()
        s = extract_spatial_mpas(ds)
        # With lon in [0, 2π] radians → [0, 360] degrees, the
        # convention should be "0..360"
        assert s["lon_convention"] == "0..360", s["lon_convention"]

    def test_returns_none_if_missing_lat_var(self):
        """A file with `nCells` dim but no `latCell` is not enough."""
        ds = _mpas_mesh_like_dataset()
        ds = ds.drop_vars("latCell")
        s = extract_spatial_mpas(ds)
        assert s is None, (
            f"expected None when latCell absent; got {s!r}")


# ────────────────────────────────────────────────────────────────────
# End-to-end via the inspect tool
# ────────────────────────────────────────────────────────────────────

class TestInspectOnMpasMesh:
    def test_inspect_returns_unstructured_envelope(self, tmp_path,
                                                    monkeypatch):
        """The full inspect flow on an MPAS mesh file produces an
        envelope with the new spatial shape. Cycle-8 spec §1 success
        criterion #1."""
        monkeypatch.chdir(tmp_path)
        ds = _mpas_mesh_like_dataset()
        p = tmp_path / "mesh.nc"
        ds.to_netcdf(p)
        env = inspect(str(p), adapter=NetCDFAdapter())
        assert env["ok"] is True, env.get("error")
        spatial = env["result"]["spatial"]
        assert spatial is not None
        assert spatial["coord_kind"] == "unstructured", (
            f"expected coord_kind='unstructured'; got {spatial!r}")
        assert spatial["cell_dim"] == "nCells"
        assert spatial["n_cells"] == 12
        assert spatial["lat_var"] == "latCell"
        assert spatial["lon_var"] == "lonCell"
        assert spatial["vertex_lat_var"] == "latVertex"
        assert spatial["vertex_lon_var"] == "lonVertex"
        assert spatial["vertices_on_cell_var"] == "verticesOnCell"
        # Convention still reported as MPAS
        assert env["result"]["convention"]["primary"] == "MPAS"

    def test_inspect_radian_converted_lat_lon_ranges(self, tmp_path,
                                                       monkeypatch):
        """Radian input → degree output in the envelope. Crash-tested
        the bug surfaced in the cycle-8 PoC pass: degenerate
        zero-meridian strips if the extractor doesn't convert."""
        monkeypatch.chdir(tmp_path)
        ds = _mpas_mesh_like_dataset()
        p = tmp_path / "mesh.nc"
        ds.to_netcdf(p)
        env = inspect(str(p), adapter=NetCDFAdapter())
        sp = env["result"]["spatial"]
        # If un-converted, lon_range would be ~[0, 2π] = [0, 6.28].
        # If converted, lon_range should be ~[0, 360].
        assert sp["lon_range"][1] > 50, (
            f"lon_range[1] = {sp['lon_range'][1]} — looks like "
            f"radians weren't converted to degrees")

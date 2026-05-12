"""MPAS convention detection.

Two real-world MPAS shapes seen during cycle-6 Phase A dogfooding:

  ocean_mesh.nc        — has Conventions = "MPAS" + lowercase nCells/nEdges
                         + MPAS coord vars (latCell, verticesOnCell, ...).
  ocn.hist.<date>.nc   — no Conventions attr, no core_name, but ships
                         uppercase NCells/NEdges/NVertLayers (Omega/MPAS
                         history files differ in casing from the mesh).

Detection must catch both. The history-file shape is the harder one —
no global attrs to lean on, only the dim fingerprint."""
import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.mpas import detect


def _mpas_mesh_like_dataset():
    """Synthetic stand-in for ocean_mesh.nc — Conventions=MPAS attr,
    lowercase mesh dims, MPAS coord variables."""
    n_cells, n_edges, n_vertices = 12, 30, 20
    ds = xr.Dataset(
        {
            "latCell": (("nCells",), np.linspace(-90.0, 90.0, n_cells)),
            "lonCell": (("nCells",), np.linspace(-180.0, 180.0, n_cells)),
            "verticesOnCell": (
                ("nCells", "maxEdges"),
                np.zeros((n_cells, 7), dtype="int32"),
            ),
            "angleEdge": (("nEdges",), np.zeros(n_edges)),
        },
        attrs={
            "Conventions": "MPAS",
            "model_name": "mpas",
            "core_name": "ocean",
            "source": "MPAS",
        },
    )
    return ds.expand_dims({"nVertices": n_vertices})


def _mpas_history_like_dataset():
    """Synthetic stand-in for ocn.hist.<date>.nc — no Conventions attr,
    uppercase NCells/NEdges/NVertLayers dims, no MPAS coord variables.
    This is the harder case: the only signal is the dim fingerprint."""
    n_cells, n_edges, n_layers = 7, 15, 4
    ds = xr.Dataset(
        {
            "Temperature": (
                ("Time", "NCells", "NVertLayers"),
                np.zeros((1, n_cells, n_layers), dtype=np.float64),
                {"standard_name": "sea_water_conservative_temperature",
                 "units": "degree_C"},
            ),
            "angleEdge": (("Time", "NEdges"), np.zeros((1, n_edges))),
        },
    )
    return ds


def test_mpas_detected_from_conventions_attr():
    ds = _mpas_mesh_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None, (
        "MPAS mesh file with Conventions='MPAS' must be detected")
    assert r["primary"] == "MPAS"
    assert r["confidence"] == "high"
    # Conventions attr was the strongest signal — must be in evidence.
    assert any("Conventions" in e for e in r["evidence"]), r["evidence"]


def test_mpas_detected_from_dim_fingerprint_alone():
    """ocn.hist files declare no global attrs. The NCells+NEdges
    dim pair (case-insensitive) is enough — these dim names don't
    occur in any other Earth-system convention we ship."""
    ds = _mpas_history_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None, (
        "MPAS history-style file (NCells+NEdges dims, no attrs) "
        "must be detected via dim fingerprint")
    assert r["primary"] == "MPAS"
    # Evidence must explain the call so users can audit the heuristic.
    ev = " ".join(r["evidence"]).lower()
    assert "ncells" in ev and "nedges" in ev, r["evidence"]


def test_mpas_detected_case_insensitive_dim_names():
    """Mesh files use lowercase nCells, history files use uppercase
    NCells. The detector must match both."""
    # Strip Conventions/source attrs so only dim fingerprint can fire
    ds = _mpas_mesh_like_dataset()
    ds = ds.drop_attrs() if hasattr(ds, "drop_attrs") else ds.assign_attrs({})
    ds.attrs = {}
    r = detect(ds, ds.attrs)
    assert r is not None, "lowercase nCells/nEdges must also be detected"
    assert r["primary"] == "MPAS"


def test_mpas_not_falsely_detected_on_generic_cf(cf_3d_file):
    """A plain CF file with lat/lon/time/plev must NOT be flagged
    as MPAS — false positives here would mis-route downstream
    convention handling."""
    ds = xr.open_dataset(cf_3d_file)
    try:
        r = detect(ds, ds.attrs)
        assert r is None, (
            f"detect() must return None for non-MPAS files; got {r!r}")
    finally:
        ds.close()


def test_mpas_not_falsely_detected_on_wrf(wrf_file):
    ds = xr.open_dataset(wrf_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_mpas_not_falsely_detected_on_roms(roms_file):
    ds = xr.open_dataset(roms_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_mpas_detected_from_attrs_only_without_mpas_dims():
    """Pathological case: someone wrote Conventions='MPAS' on a file
    that does NOT have the dim fingerprint (e.g. an annotated subset).
    The attr alone is still a valid signal — don't drop it."""
    ds = xr.Dataset(
        {"foo": (("x",), np.zeros(3))},
        attrs={"Conventions": "MPAS"},
    )
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "MPAS"


def test_inspect_reports_mpas_on_mesh_like_file(tmp_path, monkeypatch):
    """End-to-end: inspect() should now report convention.primary='MPAS'
    on the mesh-like file shape. Previously it returned primary='CF'
    (low confidence) because of soft signals, masking the file's true
    nature."""
    from src.mcp.netcdf_reader.adapter import NetCDFAdapter
    from src.mcp.netcdf_reader.tools.inspect import inspect
    monkeypatch.chdir(tmp_path)
    ds = _mpas_mesh_like_dataset()
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)
    env = inspect(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["convention"]["primary"] == "MPAS", (
        f"expected primary=MPAS; got {env['result']['convention']!r}")


def test_inspect_reports_mpas_on_history_like_file(tmp_path, monkeypatch):
    """End-to-end on the harder shape — no attrs, dim-fingerprint only."""
    from src.mcp.netcdf_reader.adapter import NetCDFAdapter
    from src.mcp.netcdf_reader.tools.inspect import inspect
    monkeypatch.chdir(tmp_path)
    ds = _mpas_history_like_dataset()
    p = tmp_path / "hist.nc"
    ds.to_netcdf(p)
    env = inspect(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["convention"]["primary"] == "MPAS", (
        f"expected primary=MPAS; got {env['result']['convention']!r}")

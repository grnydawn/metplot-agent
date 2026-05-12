# tests/mcp/netcdf_reader/unit/test_inspect.py
import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def test_inspect_cf_4d_returns_success_envelope(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(cf_4d_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_single"
    assert r["files"] == [str(cf_4d_file)]
    assert r["convention"]["primary"] == "CF"
    var_names = [v["name"] for v in r["variables"]]
    assert "ta" in var_names
    assert r["time"]["n"] == 3
    assert r["spatial"]["coord_kind"] == "rectilinear"
    assert r["vertical"]["kind"] == "pressure"


def test_inspect_uses_cache_on_second_call(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env1 = inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    # Second call should return same payload — and we can detect cache by
    # checking that the cache file exists.
    cache_dir = tmp_path / ".metplot" / "inspections"
    assert cache_dir.exists()
    files = list(cache_dir.glob("*.json"))
    assert len(files) == 1
    env2 = inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    assert env1["result"] == env2["result"]


def test_inspect_invalidates_cache_on_mtime_change(cf_3d_file, tmp_path, monkeypatch):
    import os
    import time
    monkeypatch.chdir(tmp_path)
    inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    cache_dir = tmp_path / ".metplot" / "inspections"
    time.sleep(0.01)
    os.utime(cf_3d_file, None)
    inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    files_after = sorted(cache_dir.glob("*.json"))
    # Different mtime → different hash → new cache entry, old still present
    assert len(files_after) == 2


def test_inspect_missing_file_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(tmp_path / "no.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is False
    # ClassifyError converted to file_not_found
    assert env["error"]["code"] in ("file_not_found", "unsupported_path_scheme")


def test_inspect_tolerates_time_dim_with_no_time_variable(tmp_path, monkeypatch):
    """Mesh-style files (MPAS ocean_mesh.nc, some restart files) declare
    a Time dim but ship no time coordinate variable. xarray fills in an
    int64 RangeIndex which crashes np.datetime_as_string. Previously
    that crash leaked through as `internal_error` with the raw Python
    exception message "input must have type NumPy datetime". The
    inspect envelope should now return `ok: true` with `time = None`
    and a structured `time_decode_failed` warning instead."""
    monkeypatch.chdir(tmp_path)
    ds = xr.Dataset(
        {"latCell": (("nCells",), np.linspace(-90.0, 90.0, 5))},
        attrs={"Conventions": "MPAS",
               "config_calendar_type": "gregorian_noleap"},
    )
    ds = ds.expand_dims({"Time": 1})
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)

    env = inspect(str(p), adapter=NetCDFAdapter())

    assert env["ok"] is True, (
        f"inspect crashed instead of degrading gracefully: "
        f"{env.get('error')}")
    assert env["result"]["time"] is None, (
        f"expected result.time = None when Time is a dim-only axis; "
        f"got {env['result']['time']!r}")
    codes = [w["code"] for w in env["warnings"]]
    assert "time_decode_failed" in codes, (
        f"expected a time_decode_failed warning when the file has a "
        f"Time dim with no decodable coord; got warnings: {codes}")


def test_inspect_mpas_mesh_shape_returns_sensible_envelope(tmp_path, monkeypatch):
    """End-to-end shape check on a synthetic MPAS mesh-like file.

    Covers the structure we encountered in the real ocean_mesh.nc
    file during cycle-6 Phase A dogfooding: Time dim with no time
    variable, multiple MPAS-flavored dims, a handful of variables
    on the unstructured mesh. The inspect tool should return a
    complete envelope with variables/dims populated even when time
    decode degrades."""
    monkeypatch.chdir(tmp_path)
    n_cells = 12
    n_edges = 30
    n_vert = 4
    ds = xr.Dataset(
        {
            "latCell": (("nCells",), np.linspace(-90.0, 90.0, n_cells)),
            "lonCell": (("nCells",), np.linspace(-180.0, 180.0, n_cells)),
            "areaCell": (("nCells",), np.ones(n_cells)),
            "bottomDepth": (("nCells",), np.linspace(0.0, 5000.0, n_cells)),
            "temperature": (
                ("Time", "nCells", "nVertLevels"),
                np.zeros((1, n_cells, n_vert), dtype=np.float64),
            ),
        },
        attrs={
            "Conventions": "MPAS",
            "model_name": "mpas",
            "core_name": "ocean",
            "source": "MPAS",
            "config_calendar_type": "gregorian_noleap",
            "config_start_time": "0000-01-01_00:00:00",
        },
    )
    # Add the nEdges dim by way of a placeholder variable
    ds = ds.assign(
        {"angleEdge": (("nEdges",), np.zeros(n_edges))}
    )
    ds = ds.expand_dims({"nVertices": 7})  # exercise extra MPAS dims
    p = tmp_path / "mesh.nc"
    ds.to_netcdf(p)

    env = inspect(str(p), adapter=NetCDFAdapter())

    assert env["ok"] is True, f"inspect crashed: {env.get('error')}"
    r = env["result"]
    # Variables we inserted are all present
    names = {v["name"] for v in r["variables"]}
    assert {"latCell", "lonCell", "areaCell", "bottomDepth",
            "temperature", "angleEdge"}.issubset(names)
    # All the MPAS dims survived
    for d in ("nCells", "nEdges", "nVertLevels", "nVertices", "Time"):
        assert d in r["dims"], f"missing dim {d!r}; got {r['dims']!r}"
    # Time degraded gracefully — the warning is the user-visible signal
    assert r["time"] is None
    assert "time_decode_failed" in [w["code"] for w in env["warnings"]]
    # Calendar / start-time attrs preserved for downstream consumers
    assert r["attrs"]["config_calendar_type"] == "gregorian_noleap"
    assert r["attrs"]["config_start_time"] == "0000-01-01_00:00:00"


def test_inspect_multifile_glob(cf_multifile_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    glob_path = str(cf_multifile_dir / "*.nc")
    env = inspect(glob_path, adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_multi"
    assert len(r["files"]) == 3
    assert r["time"]["n"] == 6
    assert "tos" in [v["name"] for v in r["variables"]]


def test_inspect_multifile_directory(cf_multifile_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(cf_multifile_dir), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_multi"
    assert len(r["files"]) == 3


def test_inspect_wrf_detected(wrf_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(wrf_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["convention"]["primary"] == "WRF"
    assert r["spatial"]["coord_kind"] == "curvilinear"
    assert r["spatial"]["lat_name"] == "XLAT"
    var_by_name = {v["name"]: v for v in r["variables"]}
    assert var_by_name["U"]["is_staggered"] is True
    assert var_by_name["U"]["grid_kind"] == "U"
    assert var_by_name["T2"]["is_staggered"] is False


def test_inspect_roms_detected(roms_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(roms_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["convention"]["primary"] == "ROMS"
    assert r["vertical"]["kind"] == "sigma"
    assert r["spatial"]["coord_kind"] == "curvilinear"

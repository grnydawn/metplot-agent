# tests/mcp/netcdf_reader/unit/test_inspect.py
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
    cache_dir = tmp_path / ".ncplot" / "inspections"
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
    cache_dir = tmp_path / ".ncplot" / "inspections"
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

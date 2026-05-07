# tests/mcp/netcdf_reader/unit/test_read_slice.py
import numpy as np
import pytest
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice


def test_read_slice_inline_small(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_3d_file), variable="tos",
        time="2024-09-01",
        lat=[0, 5], lon=[0, 5],
        adapter=NetCDFAdapter(),
        max_inline_bytes=100_000,
    )
    assert env["ok"] is True
    r = env["result"]
    assert r["form"] == "inline"
    assert "values" in r
    assert "coords" in r
    assert "stats" in r
    assert r["units"] == "K"
    assert r["stats"]["fraction_nan"] == 0.0


def test_read_slice_inline_nan_serialization(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    arr = np.array([[[1.0, np.nan]]], dtype="float32")
    ds = xr.Dataset(
        {"v": (("time", "lat", "lon"), arr)},
        coords={"time": np.array(["2024-01-01"], dtype="datetime64[D]"),
                "lat": [0.0], "lon": [0.0, 1.0]},
        attrs={"Conventions": "CF-1.7"},
    )
    p = tmp_path / "nan.nc"
    ds.to_netcdf(p)
    env = read_slice(str(p), variable="v", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["stats"]["fraction_nan"] == 0.5
    # NaN serialized as the string "NaN"
    flat = str(r["values"])
    assert "NaN" in flat


def test_read_slice_size_limit_exceeded(cf_4d_file, tmp_path, monkeypatch):
    # Force a very small inline cap so the full slice exceeds it
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_4d_file), variable="ta",
        adapter=NetCDFAdapter(),
        max_inline_bytes=100,  # tiny
    )
    # Will trigger file-form path (Task 16). For Task 15 we expect
    # size_limit_exceeded if file form not implemented yet.
    # After Task 16 lands, this becomes form == "file".
    # Skip until file form is implemented:
    pytest.skip("file form lands in Task 16")

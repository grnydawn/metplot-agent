"""Cycle 12 task 1 — hyperslab with stride (ncks -d parity).

read_slice(..., index_selectors={dim: [start, stop, stride]})
slices a variable along one or more dims using index-based
hyperslab semantics that mirror ncks -d dim,min,max,stride:

  * stride defaults to 1 (entry may be [start, stop] or
    [start, stop, stride]).
  * stop is INCLUSIVE (ncks docs: "min and max are inclusive").
  * dim name resolved case-insensitively against da.dims.
  * mutually exclusive with the named-axis selector on the
    same dim (time/level/lat/lon/cell_index/cell_indices).
  * different dims: fine to combine.

This file pins the spec/resolve layer + the resulting array
shape. The bit-exact ncks-comparison lives in the integration
test_ncks_parity.py file.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice


def _fixture(tmp_path: Path) -> Path:
    """4D synthetic var (time, lev, lat, lon) — values are
    deterministic so test asserts can be exact."""
    n_time, n_lev, n_lat, n_lon = 12, 5, 20, 30
    rng = np.random.default_rng(42)
    data = rng.uniform(-2.0, 30.0,
                        (n_time, n_lev, n_lat, n_lon)).astype("float64")
    ds = xr.Dataset(
        {"T": (("time", "lev", "lat", "lon"), data, {"units": "K"})},
        coords={
            "time": np.arange(n_time, dtype="int64"),
            "lev": np.linspace(0, 1000, n_lev, dtype="float64"),
            "lat": np.linspace(-89.5, 89.5, n_lat, dtype="float64"),
            "lon": np.linspace(-179.5, 179.5, n_lon, dtype="float64"),
        },
        attrs={"Conventions": "CF-1.7"},
    )
    p = tmp_path / "fixture.nc"
    ds.to_netcdf(p)
    return p


def test_single_dim_no_stride(tmp_path: Path, monkeypatch):
    """index_selectors={time: [0, 5]} — stride default 1, stop
    inclusive → 6 timesteps (0..5)."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 5]},
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # 6 timesteps × 5 lev × 20 lat × 30 lon
    assert r["shape"] == [6, 5, 20, 30]


def test_single_dim_with_stride(tmp_path: Path, monkeypatch):
    """index_selectors={time: [0, 11, 2]} → indices 0,2,4,6,8,10 → 6."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 11, 2]},
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [6, 5, 20, 30]


def test_multi_dim_mixed_strides(tmp_path: Path, monkeypatch):
    """Combine two dims with different strides."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 11, 3], "lat": [0, 19, 4]},
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # time: 0,3,6,9 → 4; lat: 0,4,8,12,16 → 5
    assert env["result"]["shape"] == [4, 5, 5, 30]


def test_dim_name_case_insensitive(tmp_path: Path, monkeypatch):
    """index_selectors uses "Time" (capitalized) — must match the
    on-disk "time" dim case-insensitively."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"Time": [0, 5]},
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [6, 5, 20, 30]


def test_stride_one_explicit(tmp_path: Path, monkeypatch):
    """Explicit stride=1 behaves identically to omitted stride."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"lat": [5, 14, 1]},
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["shape"] == [12, 5, 10, 30]


def test_values_match_numpy_isel_with_stride(tmp_path: Path, monkeypatch):
    """The values returned must equal a direct numpy stride slice
    of the source — this is the bit-exact pre-check for the
    ncks-parity comparison test."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 11, 2], "lev": [0, 4, 2]},
        adapter=NetCDFAdapter(),
        max_inline_bytes=10_000_000,  # keep inline for direct compare
    )
    assert env["ok"] is True, env.get("error")
    got = np.asarray(env["result"]["values"])
    # Independently load the file and stride-slice
    ds = xr.open_dataset(p)
    expected = ds["T"].values[0:12:2, 0:5:2, :, :]
    ds.close()
    assert got.shape == expected.shape
    assert np.array_equal(got, expected)


def test_invalid_bad_dim_name(tmp_path: Path, monkeypatch):
    """index_selectors references a dim the variable doesn't have."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"nonexistent": [0, 1]},
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]


def test_invalid_start_out_of_bounds(tmp_path: Path, monkeypatch):
    """start < 0 → invalid_spec or out_of_bounds."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [-1, 5]},
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "invalid_spec", "out_of_bounds", "internal_error"), \
        env["error"]["code"]


def test_invalid_stop_out_of_bounds(tmp_path: Path, monkeypatch):
    """stop >= dim_size → out_of_bounds."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 99]},
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "invalid_spec", "out_of_bounds", "internal_error"), \
        env["error"]["code"]


def test_invalid_negative_stride(tmp_path: Path, monkeypatch):
    """stride < 1 is not allowed (ncks rejects this too)."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 5, 0]},
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]


def test_invalid_same_dim_conflict_with_time(tmp_path: Path, monkeypatch):
    """index_selectors={time: [0,5]} + time="first" → both target
    the time dim, which is a same-dim conflict."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0, 5]},
        time="first",
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]


def test_invalid_same_dim_conflict_with_lat(tmp_path: Path, monkeypatch):
    """index_selectors={lat: [0,5]} + lat=[-45, 45] → same-dim
    conflict on the lat dim."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"lat": [0, 5]},
        lat=[-45, 45],
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]


def test_different_dim_combination_ok(tmp_path: Path, monkeypatch):
    """index_selectors on lat is fine if time= targets the time
    dim — different dims, no conflict."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"lat": [0, 9]},
        time="first",  # different dim
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # time isel with a scalar drops the dim (xarray semantics); lat
    # narrows to 10; lev/lon untouched.
    assert env["result"]["shape"] == [5, 10, 30]


def test_bad_index_selectors_value_shape(tmp_path: Path, monkeypatch):
    """Entry must be 2 or 3 ints; [start] alone or [s,e,st,extra]
    → invalid."""
    monkeypatch.chdir(tmp_path)
    p = _fixture(tmp_path)
    env = read_slice(
        str(p), variable="T",
        index_selectors={"time": [0]},
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error"), \
        env["error"]["code"]

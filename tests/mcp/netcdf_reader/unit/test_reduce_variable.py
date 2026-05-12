"""Cycle 12 task 2 — reduce_variable (ncks -y parity).

reduce_variable(path, variable, reduce_dims, op) collapses a
variable along the named dims using one of {avg, min, max, sum,
rms, total}. `total` is an ncks alias for `sum`; both must
produce identical results.

  * reduce_dims=[] collapses all dims to a scalar (parallels
    ncks -y avg -a all).
  * reduce_dims=["lat", "lon"] collapses two dims; remaining
    dims appear in result["dims"] in original order.
  * dim names case-insensitive.

The bit-exact ncks-comparison lives in
test_ncks_parity.py.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.reduce_variable import reduce_variable


def _fixture(tmp_path: Path) -> tuple[Path, np.ndarray]:
    """4D synthetic var. Returns (path, expected_data_array)."""
    n_time, n_lev, n_lat, n_lon = 4, 3, 6, 8
    rng = np.random.default_rng(7)
    data = rng.uniform(0.5, 30.0,
                        (n_time, n_lev, n_lat, n_lon)).astype("float64")
    ds = xr.Dataset(
        {"T": (("time", "lev", "lat", "lon"), data, {"units": "K"})},
        coords={
            "time": np.arange(n_time, dtype="int64"),
            "lev": np.linspace(1000, 0, n_lev),
            "lat": np.linspace(-89.5, 89.5, n_lat),
            "lon": np.linspace(-179.5, 179.5, n_lon),
        },
        attrs={"Conventions": "CF-1.7"},
    )
    p = tmp_path / "reduce_fixture.nc"
    ds.to_netcdf(p)
    return p, data


def test_avg_over_single_dim(tmp_path: Path):
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    expected = data.mean(axis=0)  # collapses time → shape (3, 6, 8)
    got = np.asarray(r["values"])
    assert got.shape == expected.shape
    assert np.array_equal(got, expected)
    assert r["dims"] == ["lev", "lat", "lon"]
    assert r["shape"] == [3, 6, 8]
    assert r["op"] == "avg"
    assert r["reduced_dims"] == ["time"]


def test_avg_over_two_dims_lat_lon(tmp_path: Path):
    """Classic 'global mean per (time, level)' pattern."""
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["lat", "lon"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    expected = data.mean(axis=(2, 3))  # → shape (4, 3)
    got = np.asarray(env["result"]["values"])
    assert got.shape == expected.shape
    assert np.array_equal(got, expected)
    assert env["result"]["dims"] == ["time", "lev"]


def test_avg_over_all_dims_scalar(tmp_path: Path):
    """reduce_dims=[] reduces over every dim → scalar."""
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=[], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    expected = float(data.mean())
    got = env["result"]["values"]
    # Result for a scalar reduction is a 0-d shape, a plain number,
    # or a 1-element list — accept any of those forms.
    if isinstance(got, list):
        assert len(got) == 1 or env["result"]["shape"] == []
        got = float(np.asarray(got).ravel()[0])
    else:
        got = float(got)
    assert got == expected
    assert env["result"]["shape"] == []
    assert env["result"]["dims"] == []


def test_sum_and_total_are_identical(tmp_path: Path):
    """`total` is an ncks alias for `sum`; the impl must treat
    them identically."""
    p, _ = _fixture(tmp_path)
    env_sum = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op="sum",
        adapter=NetCDFAdapter())
    env_ttl = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op="total",
        adapter=NetCDFAdapter())
    assert env_sum["ok"] and env_ttl["ok"]
    assert np.array_equal(
        np.asarray(env_sum["result"]["values"]),
        np.asarray(env_ttl["result"]["values"]))


def test_min_max_match_numpy(tmp_path: Path):
    p, data = _fixture(tmp_path)
    for op, np_fn in [("min", np.min), ("max", np.max)]:
        env = reduce_variable(
            str(p), variable="T", reduce_dims=["lat", "lon"], op=op,
            adapter=NetCDFAdapter())
        assert env["ok"] is True, env.get("error")
        expected = np_fn(data, axis=(2, 3))
        got = np.asarray(env["result"]["values"])
        assert np.array_equal(got, expected), (
            f"{op} diverged from numpy")


def test_sum_matches_numpy(tmp_path: Path):
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["lat"], op="sum",
        adapter=NetCDFAdapter())
    expected = data.sum(axis=2)
    got = np.asarray(env["result"]["values"])
    assert np.array_equal(got, expected)


def test_rms_matches_definition(tmp_path: Path):
    """rms = sqrt(mean(x**2)) along the reduce dims."""
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op="rms",
        adapter=NetCDFAdapter())
    expected = np.sqrt(np.mean(data ** 2, axis=0))
    got = np.asarray(env["result"]["values"])
    # RMS does sqrt — may differ in last ULP across platforms; allow
    # a very tight tolerance, but keep the structural shape check.
    assert got.shape == expected.shape
    assert np.allclose(got, expected, rtol=1e-12, atol=0)


def test_dim_name_case_insensitive(tmp_path: Path):
    p, data = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["TIME"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    expected = data.mean(axis=0)
    got = np.asarray(env["result"]["values"])
    assert np.array_equal(got, expected)


def test_invalid_op(tmp_path: Path):
    p, _ = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op="median",
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error")


def test_invalid_dim_name(tmp_path: Path):
    p, _ = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["nonexistent"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in ("invalid_spec", "internal_error")


def test_unknown_variable(tmp_path: Path):
    p, _ = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="not_there", reduce_dims=["time"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is False
    # accept ambiguous (close-match suggestion path) or invalid_spec
    assert env["error"]["code"] in (
        "ambiguous", "invalid_spec", "internal_error")


def test_remaining_dim_order_preserved(tmp_path: Path):
    """Reducing dims in arbitrary order must leave remaining dims
    in their on-disk order."""
    p, _ = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["lon", "time"], op="avg",
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    # Original order: time, lev, lat, lon → after reducing time+lon: lev, lat
    assert env["result"]["dims"] == ["lev", "lat"]


@pytest.mark.parametrize("op", ["avg", "min", "max", "sum", "rms", "total"])
def test_op_accepted(tmp_path: Path, op: str):
    """Smoke-test every supported op returns ok=True."""
    p, _ = _fixture(tmp_path)
    env = reduce_variable(
        str(p), variable="T", reduce_dims=["time"], op=op,
        adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")

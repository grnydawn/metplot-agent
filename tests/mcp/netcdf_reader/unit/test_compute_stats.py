# tests/mcp/netcdf_reader/unit/test_compute_stats.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.compute_stats import compute_stats


def test_compute_stats_returns_required_fields(cf_3d_file):
    env = compute_stats(str(cf_3d_file), variable="tos", adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    for k in ("min", "max", "mean", "std", "count",
              "fraction_nan", "percentiles", "units", "shape_summarized"):
        assert k in r
    assert set(r["percentiles"].keys()) == {"p5", "p50", "p95"}


def test_compute_stats_numeric_correctness(tmp_path):
    import xarray as xr, numpy as np
    arr = np.arange(100, dtype="float32").reshape(10, 10)
    ds = xr.Dataset({"v": (("y", "x"), arr)},
                    attrs={"Conventions": "CF-1.7"})
    p = tmp_path / "x.nc"; ds.to_netcdf(p)
    env = compute_stats(str(p), variable="v", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["min"] == 0.0
    assert r["max"] == 99.0
    assert abs(r["mean"] - 49.5) < 1e-3
    assert r["count"] == 100
    assert r["fraction_nan"] == 0.0

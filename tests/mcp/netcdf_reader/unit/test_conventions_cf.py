# tests/mcp/netcdf_reader/unit/test_conventions_cf.py
import xarray as xr
from src.mcp.netcdf_reader.conventions.cf import detect


def test_detect_cf_from_global_attr(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    result = detect(ds, ds.attrs)
    assert result["primary"] == "CF"
    assert result["confidence"] == "high"
    assert any("Conventions" in e for e in result["evidence"])
    assert result["candidates"] is None
    ds.close()


def test_detect_no_conventions_attr(tmp_path):
    # File without Conventions attr — low confidence, candidates list
    import numpy as np
    ds = xr.Dataset({"x": (("y",), np.array([1, 2, 3]))})
    p = tmp_path / "blank.nc"
    ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result["primary"] in ("CF", "unknown")
    if result["primary"] == "unknown":
        assert result["candidates"] is not None
    ds2.close()


def test_detect_cmip_from_mip_era(tmp_path):
    import numpy as np
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"),
                 np.zeros((1, 2, 2), dtype="float32"))},
        attrs={"Conventions": "CF-1.7", "mip_era": "CMIP6", "experiment_id": "historical"},
    )
    p = tmp_path / "cmip.nc"
    ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result["primary"] == "CMIP"
    assert any("mip_era" in e for e in result["evidence"])
    ds2.close()

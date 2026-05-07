# tests/mcp/netcdf_reader/unit/test_conventions_cf.py
import xarray as xr
from src.mcp.netcdf_reader.conventions.cf import detect
from src.mcp.netcdf_reader.conventions.cf import (
    extract_variables, extract_time, extract_spatial, extract_vertical,
)


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


def test_extract_variables_includes_long_name_units(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    vars_out = extract_variables(ds)
    assert len(vars_out) == 1
    v = vars_out[0]
    assert v["name"] == "ta"
    assert v["long_name"] == "Air Temperature"
    assert v["units"] == "K"
    assert v["standard_name"] == "air_temperature"
    assert v["dims"] == ["time", "plev", "lat", "lon"]
    assert v["shape"] == [3, 4, 19, 72]
    assert v["dtype"] == "float32"
    assert v["is_staggered"] is False
    ds.close()


def test_extract_time_basic(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    t = extract_time(ds)
    assert t["name"] == "time"
    assert t["n"] == 3
    assert t["monotonic"] == "increasing"
    assert t["calendar"] in ("standard", "proleptic_gregorian", "gregorian")
    assert t["range"][0].startswith("2024-09-01")
    ds.close()


def test_extract_spatial_rectilinear_360_convention(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    s = extract_spatial(ds)
    assert s["coord_kind"] == "rectilinear"
    assert s["lat_name"] == "lat"
    assert s["lon_name"] == "lon"
    assert s["lon_convention"] == "0..360"
    ds.close()


def test_extract_spatial_neg180_convention(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    s = extract_spatial(ds)
    assert s["lon_convention"] == "-180..180"
    ds.close()


def test_extract_vertical_pressure_levels(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    v = extract_vertical(ds)
    assert v["name"] == "plev"
    assert v["kind"] == "pressure"
    assert v["n"] == 4
    assert v["monotonic"] == "decreasing"
    ds.close()


def test_extract_vertical_none_for_3d(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert extract_vertical(ds) is None
    ds.close()

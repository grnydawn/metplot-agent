import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.wrf import detect


def test_wrf_detected_from_title(wrf_file):
    ds = xr.open_dataset(wrf_file)
    result = detect(ds, ds.attrs)
    assert result["primary"] == "WRF"
    assert result["confidence"] == "high"
    assert any("TITLE" in e for e in result["evidence"])
    ds.close()


def test_non_wrf_returns_none(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    result = detect(ds, ds.attrs)
    assert result is None
    ds.close()


def test_wrf_detected_from_staggered_dims(tmp_path):
    """File with WRF-style staggered dims but no TITLE attr."""
    ds = xr.Dataset(
        {"x": (("south_north", "west_east_stag"),
               np.zeros((3, 4), dtype="float32"))},
    )
    p = tmp_path / "noattr.nc"
    ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result is not None
    assert result["primary"] == "WRF"
    assert result["confidence"] in ("medium", "low")
    ds2.close()

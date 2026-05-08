# tests/mcp/plot_renderer/unit/test_slice_loader.py
import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.slice_loader import (
    NetCDFSliceLoader, SliceFileUnreadable,
)


@pytest.fixture
def slice_file(tmp_path):
    p = tmp_path / "slice.nc"
    ds = xr.Dataset(
        {"v": (("lat", "lon"), np.arange(6, dtype="f4").reshape(2, 3),
               {"units": "K", "long_name": "demo"})},
        coords={"lat": [0.0, 1.0], "lon": [0.0, 1.0, 2.0]},
        attrs={"Conventions": "CF-1.7"},
    )
    ds.to_netcdf(p, engine="netcdf4")
    return p


def test_load_returns_named_variable(slice_file):
    loader = NetCDFSliceLoader()
    da = loader.load({"path": str(slice_file), "format": "netcdf",
                      "variable": "v"})
    assert da.shape == (2, 3)
    assert da.attrs["units"] == "K"


def test_load_missing_variable_raises(slice_file):
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable) as exc:
        loader.load({"path": str(slice_file), "format": "netcdf",
                     "variable": "does_not_exist"})
    assert "does_not_exist" in str(exc.value)


def test_load_missing_path_raises():
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable):
        loader.load({"path": "/does/not/exist.nc", "format": "netcdf",
                     "variable": "v"})


def test_load_unknown_format_raises():
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable) as exc:
        loader.load({"path": "x", "format": "zarr", "variable": "v"})
    assert "format" in str(exc.value).lower()


def test_format_specific_marker():
    from src.mcp.plot_renderer import slice_loader as mod
    assert getattr(mod, "__format_specific__", False) is True

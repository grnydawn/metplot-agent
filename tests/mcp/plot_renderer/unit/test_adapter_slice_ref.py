# tests/mcp/plot_renderer/unit/test_adapter_slice_ref.py
import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.adapter import (
    InvalidSpecError, normalize_2d_any_form,
)


@pytest.fixture
def slice_file(tmp_path):
    p = tmp_path / "slice.nc"
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 1.0, 2.0])
    values = np.arange(6, dtype="f4").reshape(2, 3)
    ds = xr.Dataset(
        {"v": (("lat", "lon"), values, {"units": "K"})},
        coords={"lat": lat, "lon": lon},
    )
    ds.to_netcdf(p, engine="netcdf4")
    return p


def test_normalize_inline_form(small_2d_dataset):
    spec = {
        "values": small_2d_dataset["v"].values.tolist(),
        "lat": small_2d_dataset["lat"].values.tolist(),
        "lon": small_2d_dataset["lon"].values.tolist(),
        "units": "K",
    }
    values, coords, meta = normalize_2d_any_form(spec)
    assert values.shape == (7, 13)
    assert meta["units"] == "K"


def test_normalize_slice_ref_form(slice_file):
    spec = {"slice_ref": {"path": str(slice_file), "format": "netcdf",
                          "variable": "v"}}
    values, coords, meta = normalize_2d_any_form(spec)
    assert values.shape == (2, 3)
    assert "lat" in coords and "lon" in coords
    assert meta["units"] == "K"


def test_both_forms_set_errors(slice_file):
    spec = {"values": [[1.0]], "lat": [0.0], "lon": [0.0],
            "slice_ref": {"path": str(slice_file), "format": "netcdf",
                          "variable": "v"}}
    with pytest.raises(InvalidSpecError):
        normalize_2d_any_form(spec)


def test_neither_form_errors():
    with pytest.raises(InvalidSpecError):
        normalize_2d_any_form({})

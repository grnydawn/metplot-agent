"""Synthetic NetCDF fixture builders. Tests should use these instead
of shipping real binary samples whenever possible."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import xarray as xr
import pytest


@pytest.fixture
def cf_4d_file(tmp_path: Path) -> Path:
    """4D CF dataset: time, plev, lat, lon."""
    times = np.array(
        ["2024-09-01T00", "2024-09-01T06", "2024-09-01T12"], dtype="datetime64[h]"
    )
    plev = np.array([1000.0, 850.0, 500.0, 250.0])
    lat = np.linspace(-90, 90, 19)
    lon = np.linspace(-180, 175, 72)
    rng = np.random.default_rng(0)
    data = rng.normal(280, 10, size=(3, 4, 19, 72)).astype("float32")
    ds = xr.Dataset(
        {
            "ta": xr.DataArray(
                data, dims=("time", "plev", "lat", "lon"),
                coords={"time": times, "plev": plev, "lat": lat, "lon": lon},
                attrs={"long_name": "Air Temperature", "units": "K",
                       "standard_name": "air_temperature"},
            ),
        },
        attrs={"Conventions": "CF-1.7", "title": "Synthetic CF 4D fixture"},
    )
    ds["plev"].attrs.update({"units": "hPa", "positive": "down",
                             "standard_name": "air_pressure"})
    ds["lat"].attrs.update({"units": "degrees_north", "standard_name": "latitude"})
    ds["lon"].attrs.update({"units": "degrees_east", "standard_name": "longitude"})
    p = tmp_path / "cf_4d.nc"
    ds.to_netcdf(p)
    return p


@pytest.fixture
def cf_3d_file(tmp_path: Path) -> Path:
    """3D CF dataset: time, lat, lon. No level dim."""
    times = np.array(["2024-09-01", "2024-09-02", "2024-09-03"], dtype="datetime64[D]")
    lat = np.linspace(-90, 90, 19)
    lon = np.linspace(0, 357.5, 144)  # 0..360 convention
    rng = np.random.default_rng(1)
    data = rng.normal(290, 5, size=(3, 19, 144)).astype("float32")
    ds = xr.Dataset(
        {
            "tos": xr.DataArray(
                data, dims=("time", "lat", "lon"),
                coords={"time": times, "lat": lat, "lon": lon},
                attrs={"long_name": "Sea Surface Temperature", "units": "K",
                       "standard_name": "sea_surface_temperature"},
            ),
        },
        attrs={"Conventions": "CF-1.7"},
    )
    ds["lat"].attrs.update({"units": "degrees_north"})
    ds["lon"].attrs.update({"units": "degrees_east"})
    p = tmp_path / "cf_3d.nc"
    ds.to_netcdf(p)
    return p


@pytest.fixture
def cf_multifile_dir(tmp_path: Path) -> Path:
    """Three CF files split on time, sortable by name."""
    import numpy as np
    import xarray as xr
    out = tmp_path / "multi"; out.mkdir()
    for i, day in enumerate(["01", "02", "03"]):
        times = np.array([f"2024-09-{day}T00", f"2024-09-{day}T12"],
                         dtype="datetime64[h]")
        lat = np.linspace(-90, 90, 9)
        lon = np.linspace(0, 350, 18)
        rng = np.random.default_rng(i)
        data = rng.normal(290, 5, size=(2, 9, 18)).astype("float32")
        ds = xr.Dataset(
            {"tos": xr.DataArray(data, dims=("time", "lat", "lon"),
                                  coords={"time": times, "lat": lat, "lon": lon},
                                  attrs={"long_name": "Sea Surface Temperature",
                                         "units": "K"})},
            attrs={"Conventions": "CF-1.7"},
        )
        ds.to_netcdf(out / f"tos_2024-09-{day}.nc")
    return out

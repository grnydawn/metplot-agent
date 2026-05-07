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


@pytest.fixture
def wrf_file(tmp_path: Path) -> Path:
    """Mimics WRF: TITLE attr, Times byte-strings, staggered dims, 2D XLAT/XLONG."""
    import numpy as np
    import xarray as xr
    n_t, n_z, n_y, n_x = 3, 4, 5, 6
    times_str = ["2024-09-01_00:00:00", "2024-09-01_06:00:00", "2024-09-01_12:00:00"]
    times = np.array([list(s.encode("ascii")) for s in times_str], dtype="S1").reshape(n_t, 19)
    xlat = np.tile(np.linspace(25, 50, n_y).reshape(n_y, 1), (1, n_x)).astype("float32")
    xlong = np.tile(np.linspace(-130, -90, n_x).reshape(1, n_x), (n_y, 1)).astype("float32")
    rng = np.random.default_rng(0)
    t2 = rng.normal(290, 5, size=(n_t, n_y, n_x)).astype("float32")
    u_stag = rng.normal(5, 2, size=(n_t, n_z, n_y, n_x + 1)).astype("float32")
    ds = xr.Dataset(
        {
            "Times": (("Time", "DateStrLen"), times),
            "T2": (("Time", "south_north", "west_east"), t2,
                   {"description": "TEMP at 2 M", "units": "K"}),
            "U": (("Time", "bottom_top", "south_north", "west_east_stag"), u_stag,
                  {"description": "x-wind component", "units": "m s-1"}),
            "XLAT": (("south_north", "west_east"), xlat, {"units": "degree_north"}),
            "XLONG": (("south_north", "west_east"), xlong, {"units": "degree_east"}),
        },
        attrs={"TITLE": "OUTPUT FROM WRF V4.5", "GRIDTYPE": "C", "MMINLU": "USGS"},
    )
    p = tmp_path / "wrfout.nc"
    ds.to_netcdf(p)
    return p


@pytest.fixture
def roms_file(tmp_path: Path) -> Path:
    """Mimics ROMS: s_rho/Cs_r vertical, lat_rho/lon_rho 2D, ocean_time."""
    import numpy as np
    import xarray as xr
    n_t, n_s, n_y, n_x = 2, 3, 4, 5
    ocean_time = np.array(
        ["2024-09-01", "2024-09-02"], dtype="datetime64[D]"
    )
    s_rho = np.linspace(-1.0, 0.0, n_s)
    cs_r = -np.linspace(0.5, 0.0, n_s)
    lat_rho = np.tile(np.linspace(30, 35, n_y).reshape(n_y, 1), (1, n_x)).astype("float32")
    lon_rho = np.tile(np.linspace(-75, -70, n_x).reshape(1, n_x), (n_y, 1)).astype("float32")
    rng = np.random.default_rng(0)
    temp = rng.normal(15, 3, size=(n_t, n_s, n_y, n_x)).astype("float32")
    ds = xr.Dataset(
        {
            "temp": (("ocean_time", "s_rho", "eta_rho", "xi_rho"), temp,
                     {"long_name": "potential temperature", "units": "C"}),
            "lat_rho": (("eta_rho", "xi_rho"), lat_rho, {"units": "degree_north"}),
            "lon_rho": (("eta_rho", "xi_rho"), lon_rho, {"units": "degree_east"}),
            "s_rho": (("s_rho",), s_rho, {"long_name": "S-coord at rho",
                                          "standard_name": "ocean_s_coordinate_g2"}),
            "Cs_r": (("s_rho",), cs_r, {"long_name": "S-coord stretching at rho"}),
        },
        coords={"ocean_time": ocean_time},
        attrs={"type": "ROMS/TOMS history file"},
    )
    p = tmp_path / "roms.nc"
    ds.to_netcdf(p)
    return p

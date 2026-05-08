"""Shared fixtures for plot-renderer tests.

Forces the matplotlib Agg backend before any test imports matplotlib so
suite runs headless on CI.
"""
import os

# Set BEFORE any matplotlib import
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib  # noqa: E402
matplotlib.use("Agg")  # idempotent

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import xarray as xr  # noqa: E402


@pytest.fixture
def small_2d_dataset() -> xr.Dataset:
    """Tiny 2D lat/lon Dataset for map tests."""
    lat = np.linspace(-30.0, 30.0, 7)
    lon = np.linspace(-60.0, 60.0, 13)
    values = np.outer(np.cos(np.deg2rad(lat)),
                      np.sin(np.deg2rad(lon))).astype("float32")
    return xr.Dataset(
        {"v": (("lat", "lon"), values, {"units": "K", "long_name": "demo"})},
        coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                "lon": ("lon", lon, {"units": "degrees_east"})},
        attrs={"Conventions": "CF-1.7"},
    )


@pytest.fixture
def small_timeseries() -> dict:
    """Single-series spec sugar."""
    times = [f"2024-{m:02d}-15T00:00" for m in range(1, 13)]
    values = np.linspace(0.0, 11.0, 12).tolist()
    return {"values": values, "time": times, "label": "demo"}


@pytest.fixture
def small_profile() -> dict:
    """Single-series profile spec sugar."""
    vertical = [1000.0, 850.0, 700.0, 500.0, 250.0, 100.0]  # hPa
    values = [288.0, 280.0, 270.0, 250.0, 220.0, 200.0]
    return {"values": values, "vertical": vertical,
            "vertical_units": "hPa", "label": "demo"}

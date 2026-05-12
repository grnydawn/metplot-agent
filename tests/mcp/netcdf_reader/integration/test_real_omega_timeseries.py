"""Cycle 11 task 4 — real-Omega timeseries + profile end-to-end.

Three timeseries reduction modes + one profile, all skipped
unless data/omega/ is on disk.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.selectors_unstructured import (
    area_weights,
    cells_in_bbox,
    find_nearest_cell,
)
from src.mcp.netcdf_reader.tools.read_slice import read_slice

REPO = Path(__file__).resolve().parents[4]
DATA = REPO / "data" / "omega"
MESH = DATA / "ocean_test_mesh.nc"
GLOB = str(DATA / "ocn.hist.000*-*-01_00.00.00.nc")
HIST_ONE = DATA / "ocn.hist.0001-02-01_00.00.00.nc"

pytestmark = pytest.mark.skipif(
    not MESH.exists(),
    reason="data/omega/ files not on disk; skip real-file integration",
)


# ── Time-series: single cell at (lat, lon) ──────────────────────

def test_single_cell_timeseries_multi_file():
    """Pick a cell in the North Atlantic (40N, ~-65W → Omega is
    0..360 so use 295E); slice Temperature[t=all, level=0,
    cell=<idx>] across the 12-file glob."""
    adapter = NetCDFAdapter()
    with xr.open_dataset(MESH, decode_times=False) as mesh_ds:
        idx = find_nearest_cell(mesh_ds, lat=40.0, lon=295.0)
    env = read_slice(
        GLOB, variable="Temperature", level=0,
        cell_index=idx, mesh_path=str(MESH),
        adapter=adapter, max_inline_bytes=10_000_000)
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # Multi-file glob concats time; NCells reduces to scalar via
    # cell_index; NVertLayers reduces via level=0. Shape = [12].
    assert r["shape"] == [12], r["shape"]


# ── Time-series: global area-weighted mean ──────────────────────

def test_global_mean_timeseries_multi_file():
    """Read all cells, level=0, all times; compute area-weighted
    mean skill-side using area_weights from the mesh."""
    adapter = NetCDFAdapter()
    env = read_slice(
        GLOB, variable="Temperature", level=0,
        mesh_path=str(MESH),
        adapter=adapter, max_inline_bytes=200_000_000)
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # Shape should be [12, 7153] (time × NCells).
    assert r["shape"] == [12, 7153], r["shape"]

    # Compute global area-weighted mean for each time step.
    with xr.open_dataset(MESH, decode_times=False) as mesh_ds:
        w = area_weights(mesh_ds)
    if r["form"] == "inline":
        values = np.asarray(r["values"], dtype=float)
    else:
        with xr.open_dataset(r["path"]) as ds:
            values = ds[list(ds.data_vars)[0]].values
    # Compute per-time area-weighted mean over cells.
    ws = w / w.sum()
    series = (values * ws[np.newaxis, :]).sum(axis=1)
    # 12 monthly means, all finite, ocean temperature ranges in
    # plausible degree_C bounds. (The Omega test fixtures ship
    # identical content across the 12 monthly files — verified by
    # opening two files directly — so the series is constant; this
    # doesn't impeach the multi-file/cell-axis machinery.)
    assert series.shape == (12,)
    assert np.isfinite(series).all()
    assert -5.0 <= float(series.min())
    assert float(series.max()) <= 35.0


# ── Time-series: regional bbox mean ─────────────────────────────

def test_regional_mean_timeseries_multi_file():
    """North Atlantic-ish bbox (20..60 lat, 280..360 lon — Omega
    is 0..360), area-weighted mean per time step."""
    adapter = NetCDFAdapter()
    with xr.open_dataset(MESH, decode_times=False) as mesh_ds:
        ids = cells_in_bbox(mesh_ds, lat_min=20.0, lat_max=60.0,
                              lon_min=280.0, lon_max=360.0)
        w = area_weights(mesh_ds, indices=ids)
    assert ids.size > 100, ids.size  # Omega has ~477 cells here
    env = read_slice(
        GLOB, variable="Temperature", level=0,
        cell_indices=ids.tolist(), mesh_path=str(MESH),
        adapter=adapter, max_inline_bytes=200_000_000)
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    assert r["shape"] == [12, ids.size], r["shape"]
    if r["form"] == "inline":
        values = np.asarray(r["values"], dtype=float)
    else:
        with xr.open_dataset(r["path"]) as ds:
            values = ds[list(ds.data_vars)[0]].values
    ws = w / w.sum()
    series = (values * ws[np.newaxis, :]).sum(axis=1)
    assert series.shape == (12,)


# ── Profile: cell-indexed single timestep, all levels ───────────

def test_single_cell_profile_single_file():
    """Pick a cell, single timestep, ALL vertical levels → shape
    = [NVertLayers] = [60]. Feeds straight into render_profile."""
    adapter = NetCDFAdapter()
    with xr.open_dataset(MESH, decode_times=False) as mesh_ds:
        idx = find_nearest_cell(mesh_ds, lat=40.0, lon=295.0)
    env = read_slice(
        str(HIST_ONE), variable="Temperature", time="first",
        cell_index=idx, mesh_path=str(MESH),
        adapter=adapter, max_inline_bytes=10_000_000)
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    # 60 vertical layers, all in degree_C.
    assert r["shape"] == [60], r["shape"]
    if r["form"] == "inline":
        values = np.asarray(r["values"], dtype=float)
    else:
        with xr.open_dataset(r["path"]) as ds:
            values = ds[list(ds.data_vars)[0]].values
    assert values.shape == (60,)

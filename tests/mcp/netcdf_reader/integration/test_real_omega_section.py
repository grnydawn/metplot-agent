"""Cycle 13 theme D — end-to-end cross-section on real Omega data.

slice_along_section + read_slice cell_indices + render_section
pipeline. Verifies the orchestration works against the bundled
real Omega monthly + mesh.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.sections import slice_along_section
from src.mcp.netcdf_reader.tools.read_slice import read_slice
from src.mcp.plot_renderer.tools.render_section import render_section


_REPO_ROOT = Path(__file__).resolve().parents[4]
_HIST = _REPO_ROOT / "data/omega/ocn.hist.0001-02-01_00.00.00.nc"
_MESH = _REPO_ROOT / "data/omega/ocean_test_mesh.nc"

pytestmark = pytest.mark.skipif(
    not (_HIST.exists() and _MESH.exists()),
    reason="data/omega/ bundled fixtures not present")


def test_great_circle_section_atlantic(tmp_path: Path, monkeypatch):
    """Sample 60 points along a great-circle from (0N, 320E) to
    (60N, 350E) — North Atlantic transect — pull Temperature at
    each cell across all 60 vertical layers, render."""
    monkeypatch.chdir(tmp_path)

    # Step 1: sample the great-circle and pick nearest cells.
    with xr.open_dataset(_MESH) as mds:
        out = slice_along_section(
            mds, lat1=0.0, lon1=320.0, lat2=60.0, lon2=350.0,
            n_samples=60)
    indices = out["cell_indices"]
    distances = out["distances_km"]
    assert len(indices) == 60

    # Step 2: fetch Temperature at all 60 levels for those cells.
    env = read_slice(
        str(_HIST), variable="Temperature", time="first",
        cell_indices=indices, mesh_path=str(_MESH),
        adapter=NetCDFAdapter(), max_inline_bytes=100_000_000)
    assert env["ok"] is True, env.get("error")
    # Shape: NCells subset comes from on-disk order. Omega is
    # (NCells, NVertLayers) → (60, 60).
    values = np.asarray(env["result"]["values"])
    assert values.shape == (60, 60)

    # Step 3: render the section.
    levels = np.arange(60, dtype=float)  # layer index as vertical
    renv = render_section({
        "values": values.tolist(),
        "distances_km": distances,
        "vertical_coord": levels.tolist(),
        "vertical_units": "depth_m",  # triggers axis inversion
        "title": "Temperature — NAtl transect (0..60N, 320..350E)",
        "units": "degree_C",
    })
    assert renv["ok"] is True, renv.get("error")
    out_path = Path(renv["result"]["output_path"])
    assert out_path.exists()
    assert out_path.stat().st_size > 10_000
    drawn = renv["result"]["oracle"]["drawn"]
    assert drawn["n_samples"] == 60
    assert drawn["n_levels"] == 60
    assert drawn["invert_vertical"] is True
    # End-to-end great-circle distance should be sensible
    # (60° latitude span alone = ~6700 km; add lon → ~7000+ km).
    assert 5000 < drawn["distance_km_total"] < 10000


def test_short_equatorial_section(tmp_path: Path, monkeypatch):
    """Short transect along the equator (10 samples)."""
    monkeypatch.chdir(tmp_path)

    with xr.open_dataset(_MESH) as mds:
        out = slice_along_section(
            mds, lat1=0.0, lon1=200.0, lat2=0.0, lon2=240.0,
            n_samples=10)
    indices = out["cell_indices"]

    env = read_slice(
        str(_HIST), variable="Temperature", time="first", level=0,
        cell_indices=indices, mesh_path=str(_MESH),
        adapter=NetCDFAdapter(), max_inline_bytes=1_000_000)
    assert env["ok"] is True, env.get("error")
    values = np.asarray(env["result"]["values"])
    # level reduced → shape (10,) — for the section render we'd
    # need 2-D, so this just verifies the slice path works.
    assert values.shape == (10,)

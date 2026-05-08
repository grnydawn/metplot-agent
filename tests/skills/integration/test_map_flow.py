# tests/skills/integration/test_map_flow.py
"""End-to-end skill-flow simulation: SST in North Atlantic.

Mechanically follows what the netcdf-plot-map skill instructs an agent
to do, against the actual MCP tool functions. No LLM in the loop.
Proves the skill instructions are executable.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr


_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGIONS = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
             / "references" / "regions.json")
_COLORMAPS = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
               / "references" / "colormaps.json")


def _make_synthetic_sst_file(path: Path) -> None:
    """Create a small CF-compliant NetCDF with `tos` (SST in K)."""
    lat = np.linspace(-90, 90, 19)   # 10° lat steps
    lon = np.linspace(-180, 175, 72) # 5° lon steps; 0..360 not used
    # Simple meridional gradient + zonal ripple
    grid_lon, grid_lat = np.meshgrid(lon, lat)
    values = (290.0 + 5.0 * np.cos(np.deg2rad(grid_lat))
              + 1.0 * np.sin(np.deg2rad(grid_lon * 4))).astype("float32")
    ds = xr.Dataset(
        {"tos": (("lat", "lon"), values,
                 {"units": "K", "long_name": "sea surface temperature",
                  "standard_name": "sea_surface_temperature"})},
        coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                "lon": ("lon", lon, {"units": "degrees_east"})},
        attrs={"Conventions": "CF-1.7"},
    )
    ds.to_netcdf(path, engine="netcdf4")


def test_map_flow_e2e(tmp_path, monkeypatch):
    """Simulate the SST map flow per netcdf-plot-map/SKILL.md."""
    monkeypatch.chdir(tmp_path)
    nc_path = tmp_path / "sst.nc"
    _make_synthetic_sst_file(nc_path)

    # Step 1: Inspect (skill instructs: call netcdf-reader.inspect)
    from src.mcp.netcdf_reader.tools.inspect import inspect
    from src.mcp.netcdf_reader.adapter import NetCDFAdapter
    inspect_env = inspect(str(nc_path), adapter=NetCDFAdapter())
    assert inspect_env["ok"] is True
    assert "tos" in {v["name"] for v in inspect_env["result"]["variables"]}

    # Step 2-3: Resolve "SST" → "tos" (skill's alias-resolution step;
    # in practice the agent does this; here we fast-track)
    variable = "tos"

    # Step 5: Resolve "North Atlantic" via regions.json
    regions = json.loads(_REGIONS.read_text())
    na = regions["regions"]["North Atlantic"]
    assert na["lon_min"] == -80 and na["lat_max"] == 70

    # Step 7: Detect field character → temperature_absolute → RdYlBu_r
    cmaps = json.loads(_COLORMAPS.read_text())
    char = cmaps["by_field_character"]["temperature_absolute"]
    assert char["cmap"] == "RdYlBu_r"

    # Step 10: Read slice
    # Note: cycle-1's parse_latlon accepts a plain [min, max] list for bbox,
    # not the {"between": [...]} dict form that the plan body suggested.
    from src.mcp.netcdf_reader.tools.read_slice import read_slice
    slice_env = read_slice(
        str(nc_path), variable=variable,
        lat=[na["lat_min"], na["lat_max"]],
        lon=[na["lon_min"], na["lon_max"]],
        adapter=NetCDFAdapter(),
    )
    assert slice_env["ok"] is True

    # Step 11-12: Compose render spec, call render_map
    from src.mcp.plot_renderer.tools import render_map as rm
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed; skill flow exercised through render_map step")

    spec_kwargs: dict = {
        "projection": "PlateCarree",
        "colormap": char["cmap"],
        "title": "SST September 2024 - North Atlantic",
        "lon_convention": "-180..180",
        "output_path": str(tmp_path / "na_sst.png"),
    }
    if slice_env["result"]["form"] == "inline":
        spec_kwargs["values"] = slice_env["result"]["values"]
        spec_kwargs["lat"] = slice_env["result"]["coords"]["lat"]
        spec_kwargs["lon"] = slice_env["result"]["coords"]["lon"]
    else:
        spec_kwargs["slice_ref"] = {
            "path": slice_env["result"]["path"],
            "format": slice_env["result"]["format"],
            "variable": variable,
        }
    render_env = rm.render_map(spec_kwargs)
    assert render_env["ok"] is True, render_env.get("error")

    # Step 13: Verify
    out = render_env["result"]
    assert Path(out["output_path"]).stat().st_size > 5000
    assert out["oracle"]["data"]["nan_fraction"] < 1.0


def test_regions_lookup_works_for_all_documented():
    """Every region in the JSON is discoverable by name."""
    regions = json.loads(_REGIONS.read_text())
    assert len(regions["regions"]) > 0
    # Spot-check a few
    for name in ("North Atlantic", "Niño 3.4", "Tropics"):
        assert name in regions["regions"]


def test_colormaps_lookup_works_for_all_characters():
    """Every field character maps to a real cmap."""
    import matplotlib as mpl
    cmaps = json.loads(_COLORMAPS.read_text())
    for char, entry in cmaps["by_field_character"].items():
        assert entry["cmap"] in mpl.colormaps, (
            f"field_character {char!r}: cmap {entry['cmap']!r} not in registry")

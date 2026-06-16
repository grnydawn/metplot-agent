import json
from pathlib import Path


def test_parses(built_plugin: Path):
    json.loads((built_plugin / "plugin.json").read_text())


def test_required_fields(built_plugin: Path):
    m = json.loads((built_plugin / "plugin.json").read_text())
    for f in ("name", "version", "description"):
        assert f in m


def test_metplot_cycle_7(built_plugin: Path):
    m = json.loads((built_plugin / "plugin.json").read_text())
    assert m["metplot"]["build_cycle"] == 7


def test_metplot_ships_skills(built_plugin: Path):
    m = json.loads((built_plugin / "plugin.json").read_text())
    assert m["metplot"]["ships_skills"] == [
        "netcdf-inspect", "netcdf-plot-map", "netcdf-plot-profile",
        "netcdf-plot-router", "netcdf-plot-timeseries", "skill-refiner",
    ]


def test_metplot_ships_mcp_servers(built_plugin: Path):
    m = json.loads((built_plugin / "plugin.json").read_text())
    assert m["metplot"]["ships_mcp_servers"] == ["netcdf-reader", "plot-renderer"]

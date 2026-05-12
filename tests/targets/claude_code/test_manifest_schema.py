# tests/targets/claude_code/test_manifest_schema.py
"""Verify plugin.json shape."""
from __future__ import annotations

import json
from pathlib import Path


def test_plugin_json_parses(built_plugin: Path) -> None:
    text = (built_plugin / ".claude-plugin" / "plugin.json").read_text()
    json.loads(text)


def test_required_fields(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    for field in ("name", "version", "description"):
        assert field in m, f"missing required field: {field}"


def test_name_pinned(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] == "metplot"


def test_metplot_block_present(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "metplot" in m
    nc = m["metplot"]
    assert nc["build_cycle"] == 4
    assert "ships_skills" in nc
    assert "ships_mcp_servers" in nc


def test_ships_skills_matches_allowlist(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    expected = {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
        "skill-refiner",
    }
    assert set(m["metplot"]["ships_skills"]) == expected


def test_ships_mcp_servers(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert set(m["metplot"]["ships_mcp_servers"]) == {
        "netcdf-reader", "plot-renderer"}


def test_skill_refiner_included(built_plugin: Path) -> None:
    """skill-refiner ships starting cycle 6 Phase B."""
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "skill-refiner" in m["metplot"]["ships_skills"]

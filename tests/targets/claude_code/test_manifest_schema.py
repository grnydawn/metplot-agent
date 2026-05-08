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
    assert m["name"] == "ncplot"


def test_ncplot_block_present(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "ncplot" in m
    nc = m["ncplot"]
    assert nc["build_cycle"] == 4
    assert "ships_skills" in nc
    assert "ships_mcp_servers" in nc


def test_ships_skills_matches_allowlist(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    expected = {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    }
    assert set(m["ncplot"]["ships_skills"]) == expected


def test_ships_mcp_servers(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert set(m["ncplot"]["ships_mcp_servers"]) == {
        "netcdf-reader", "plot-renderer"}


def test_skill_refiner_excluded(built_plugin: Path) -> None:
    """skill-refiner is cycle 6; must NOT be advertised in cycle 4."""
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "skill-refiner" not in m["ncplot"]["ships_skills"]

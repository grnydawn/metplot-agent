# tests/targets/claude_code/test_mcp_json_schema.py
"""Verify .mcp.json contents."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


_EXPECTED_SERVERS_BY_EXTERNAL_NAME = {
    "netcdf-reader": "ncplot-netcdf-reader",
    "plot-renderer": "ncplot-plot-renderer",
}


def test_mcp_json_parses(built_plugin: Path) -> None:
    json.loads((built_plugin / ".mcp.json").read_text())


def test_has_mcp_servers_key(built_plugin: Path) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    assert "mcpServers" in d
    assert isinstance(d["mcpServers"], dict)


def test_all_expected_servers_listed(built_plugin: Path) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    assert set(d["mcpServers"].keys()) == set(_EXPECTED_SERVERS_BY_EXTERNAL_NAME)


@pytest.mark.parametrize(
    "external_name,entry_point",
    sorted(_EXPECTED_SERVERS_BY_EXTERNAL_NAME.items()),
)
def test_each_server_uses_entry_point_command(
    built_plugin: Path, external_name: str, entry_point: str,
) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    server = d["mcpServers"][external_name]
    assert server["command"] == entry_point, (
        f"{external_name}: command {server['command']!r} != "
        f"expected entry-point {entry_point!r}")
    assert "args" in server
    assert isinstance(server["args"], list)

"""IMPORTANT: Copilot's .vscode/mcp.json uses `servers` key, not `mcpServers`.

This is the only host with this naming. Other targets use `mcpServers`.
If this test ever fails, check for cross-target copy-paste contamination.
"""
import json
from pathlib import Path

import pytest


def test_uses_servers_not_mcpServers(built_plugin: Path):
    d = json.loads((built_plugin / ".vscode" / "mcp.json").read_text())
    assert "servers" in d, "Copilot expects 'servers' key in .vscode/mcp.json"
    assert "mcpServers" not in d, (
        "Copilot does NOT use 'mcpServers' (that's Claude Code / Cursor / "
        "Gemini convention)")


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "metplot-netcdf-reader"),
     ("plot-renderer", "metplot-plot-renderer")],
)
def test_each_server_uses_entry_point(
    built_plugin: Path, external_name: str, entry_point: str,
):
    d = json.loads((built_plugin / ".vscode" / "mcp.json").read_text())
    s = d["servers"][external_name]
    assert s["command"] == entry_point

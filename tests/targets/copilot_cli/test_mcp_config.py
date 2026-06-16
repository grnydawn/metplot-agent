"""AC3/AC4 — the distinguishing surface for the standalone Copilot CLI.

The CLI reads `~/.copilot/mcp-config.json` keyed on `mcpServers` (NOT
`servers`), with per-server `type: "local"` stdio entries. This is the
deliberate contrast vs `targets/copilot/`, which emits `.vscode/mcp.json`
keyed on `servers`. If `mcpServers`/`servers` ever swap here, it's a
cross-target copy-paste regression.
"""
import json
from pathlib import Path

import pytest


def _config(built_plugin: Path) -> dict:
    return json.loads((built_plugin / "mcp-config.json").read_text())


def test_uses_mcpServers_not_servers(built_plugin: Path):
    d = _config(built_plugin)
    assert "mcpServers" in d, (
        "standalone Copilot CLI expects 'mcpServers' key in mcp-config.json")
    assert "servers" not in d, (
        "standalone Copilot CLI does NOT use the VS Code plugin's 'servers' "
        "key — that's targets/copilot/.vscode/mcp.json")


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "metplot-netcdf-reader"),
     ("plot-renderer", "metplot-plot-renderer")],
)
def test_each_server_local_stdio(
    built_plugin: Path, external_name: str, entry_point: str,
):
    d = _config(built_plugin)
    s = d["mcpServers"][external_name]
    assert s["type"] == "local"
    assert s["command"] == entry_point
    assert s["args"] == []
    assert s["tools"] == ["*"]

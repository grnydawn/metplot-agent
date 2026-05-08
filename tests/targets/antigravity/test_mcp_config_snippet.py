import json
from pathlib import Path

def test_snippet_parses(built_plugin: Path):
    json.loads((built_plugin / "mcp_config.json").read_text())

def test_uses_mcpServers_key(built_plugin: Path):
    d = json.loads((built_plugin / "mcp_config.json").read_text())
    assert "mcpServers" in d  # Antigravity uses mcpServers (same as Claude Desktop)
    for name in ("netcdf-reader", "plot-renderer"):
        assert name in d["mcpServers"]

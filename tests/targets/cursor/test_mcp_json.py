import json
from pathlib import Path
import pytest


def test_at_cursor_subdir(built_plugin: Path):
    assert (built_plugin / ".cursor" / "mcp.json").is_file()


def test_uses_mcpServers_key(built_plugin: Path):
    """Cursor uses mcpServers (same as Claude Code), NOT 'servers' (Copilot)."""
    d = json.loads((built_plugin / ".cursor" / "mcp.json").read_text())
    assert "mcpServers" in d
    assert "servers" not in d


@pytest.mark.parametrize("external_name,entry_point",
    [("netcdf-reader", "ncplot-netcdf-reader"),
     ("plot-renderer", "ncplot-plot-renderer")])
def test_entry_point(built_plugin: Path, external_name: str, entry_point: str):
    d = json.loads((built_plugin / ".cursor" / "mcp.json").read_text())
    assert d["mcpServers"][external_name]["command"] == entry_point

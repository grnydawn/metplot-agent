import json
from pathlib import Path
import pytest


def test_snippet_parses(built_plugin: Path):
    json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())


def test_uses_mcpServers_key(built_plugin: Path):
    d = json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())
    assert "mcpServers" in d


@pytest.mark.parametrize("name,entry", [
    ("netcdf-reader", "metplot-netcdf-reader"),
    ("plot-renderer", "metplot-plot-renderer"),
])
def test_each_uses_entry_point(built_plugin: Path, name: str, entry: str):
    d = json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())
    assert d["mcpServers"][name]["command"] == entry

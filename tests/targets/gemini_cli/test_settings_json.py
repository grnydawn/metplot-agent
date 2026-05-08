# tests/targets/gemini_cli/test_settings_json.py
import json
from pathlib import Path
import pytest


def test_settings_parses(built_plugin: Path):
    json.loads((built_plugin / "settings.json").read_text())


def test_has_mcp_servers_key(built_plugin: Path):
    d = json.loads((built_plugin / "settings.json").read_text())
    assert "mcpServers" in d


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "metplot-netcdf-reader"),
     ("plot-renderer", "metplot-plot-renderer")],
)
def test_each_server_entry_point(built_plugin: Path, external_name: str, entry_point: str):
    d = json.loads((built_plugin / "settings.json").read_text())
    s = d["mcpServers"][external_name]
    assert s["command"] == entry_point

# tests/targets/codex/test_config_toml.py
import sys
from pathlib import Path

import pytest

# Python 3.11+ has tomllib; fall back to tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _load(p: Path) -> dict:
    return tomllib.loads(p.read_text())


def test_parses_as_toml(built_plugin: Path):
    _load(built_plugin / "config.toml")


def test_has_mcp_servers_section(built_plugin: Path):
    d = _load(built_plugin / "config.toml")
    assert "mcp_servers" in d


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "metplot-netcdf-reader"),
     ("plot-renderer", "metplot-plot-renderer")],
)
def test_each_server_uses_entry_point(
    built_plugin: Path, external_name: str, entry_point: str,
):
    d = _load(built_plugin / "config.toml")
    s = d["mcp_servers"][external_name]
    assert s["type"] == "stdio"
    assert s["command"] == entry_point
    assert s["args"] == []

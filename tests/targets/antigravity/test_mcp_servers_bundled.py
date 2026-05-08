# tests/targets/antigravity/test_mcp_servers_bundled.py
from pathlib import Path

import pytest


_SERVERS = ("netcdf_reader", "plot_renderer")


@pytest.mark.parametrize("server", _SERVERS)
def test_re_rooted_source(built_plugin: Path, server: str):
    pkg = built_plugin / "mcp-servers" / server / "src" / "mcp" / server
    assert pkg.is_dir()
    assert (pkg / "server.py").is_file()


@pytest.mark.parametrize("server", _SERVERS)
def test_pyproject_patched(built_plugin: Path, server: str):
    text = (built_plugin / "mcp-servers" / server / "pyproject.toml").read_text()
    assert "[tool.setuptools.packages.find]" in text
    assert 'where = ["src"]' in text

# tests/targets/claude_code/test_mcp_servers_bundled.py
"""Verify each MCP server is bundled with re-rooted source + patched pyproject."""
from __future__ import annotations

from pathlib import Path

import pytest


_EXPECTED_SERVERS = {"netcdf_reader", "plot_renderer"}


def test_mcp_servers_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / "mcp-servers").is_dir()


def test_all_expected_servers_present(built_plugin: Path) -> None:
    actual = {p.name for p in (built_plugin / "mcp-servers").iterdir() if p.is_dir()}
    assert actual == _EXPECTED_SERVERS


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_pyproject_present(built_plugin: Path, server: str) -> None:
    pp = built_plugin / "mcp-servers" / server / "pyproject.toml"
    assert pp.is_file()


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_pyproject_has_packages_find_block(built_plugin: Path, server: str) -> None:
    """Patched pyproject.toml must enable setuptools.packages.find against src/."""
    text = (built_plugin / "mcp-servers" / server / "pyproject.toml").read_text()
    assert "[tool.setuptools.packages.find]" in text, (
        f"{server}: pyproject.toml missing [tool.setuptools.packages.find]")
    assert 'where = ["src"]' in text, (
        f"{server}: pyproject.toml missing where = [\"src\"]")


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_source_re_rooted_under_src_mcp(built_plugin: Path, server: str) -> None:
    """The bundled package source must be at <server>/src/mcp/<server>/ to
    preserve the `from src.mcp.<server>...` import path."""
    pkg_dir = built_plugin / "mcp-servers" / server / "src" / "mcp" / server
    assert pkg_dir.is_dir(), f"missing re-rooted package dir: {pkg_dir}"
    assert (pkg_dir / "__init__.py").is_file()
    assert (pkg_dir / "server.py").is_file()


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_no_stray_top_level_python_files(built_plugin: Path, server: str) -> None:
    """The bundled <server>/ should NOT have stray python files at top level
    (only pyproject.toml + optional README + src/)."""
    server_dir = built_plugin / "mcp-servers" / server
    py_at_root = list(server_dir.glob("*.py"))
    assert not py_at_root, (
        f"{server}: stray .py files at bundle root: {[p.name for p in py_at_root]}")

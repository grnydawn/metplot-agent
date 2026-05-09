# tests/tools/test_install_deps_launchers.py
"""Unit tests for the cycle-6 launcher-generation feature.

write_launchers() emits one shell shim per discovered MCP server entry
point so the plugin's `.mcp.json` can find servers via the plugin's
own bin/ on PATH instead of needing the install venv to be activated.
"""
from __future__ import annotations

import os
import stat
from pathlib import Path

import pytest

from tools.install_deps import (
    parse_args,
    parse_project_scripts,
    write_launchers,
)


_PYPROJECT_TEMPLATE = """\
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "{name}"
version = "0.1.0"

[project.scripts]
{entry_point} = "{module}:main"

[tool.setuptools.packages.find]
include = ["src", "src.*"]
namespaces = true
"""


def _make_server(root: Path, dirname: str, entry_point: str, module: str) -> Path:
    """Materialise a minimal mcp-servers/<dirname>/pyproject.toml on disk."""
    server = root / dirname
    server.mkdir(parents=True)
    (server / "pyproject.toml").write_text(
        _PYPROJECT_TEMPLATE.format(
            name=entry_point, entry_point=entry_point, module=module,
        )
    )
    return server


def test_parse_project_scripts_extracts_entries(tmp_path):
    pp = tmp_path / "pyproject.toml"
    pp.write_text(
        '[project]\nname = "foo"\n\n'
        '[project.scripts]\n'
        'metplot-foo = "src.mcp.foo.server:main"\n'
        'metplot-bar = "src.mcp.bar.server:main"  # trailing comment\n\n'
        '[tool.setuptools.packages.find]\nwhere = ["src"]\n'
    )
    entries = list(parse_project_scripts(pp))
    assert entries == [
        ("metplot-foo", "src.mcp.foo.server:main"),
        ("metplot-bar", "src.mcp.bar.server:main"),
    ]


def test_parse_project_scripts_ignores_other_tables(tmp_path):
    pp = tmp_path / "pyproject.toml"
    pp.write_text(
        '[project.optional-dependencies]\n'
        'dev = ["pytest>=7"]\n'
        '[project.scripts]\n'
        'metplot-x = "src.mcp.x.server:main"\n'
        '[tool.setuptools]\n'
        'should-be-ignored = "yes"\n'
    )
    entries = list(parse_project_scripts(pp))
    assert entries == [("metplot-x", "src.mcp.x.server:main")]


def test_parse_project_scripts_returns_empty_when_block_missing(tmp_path):
    pp = tmp_path / "pyproject.toml"
    pp.write_text('[project]\nname = "foo"\n')
    assert list(parse_project_scripts(pp)) == []


@pytest.mark.skipif(os.name == "nt", reason="POSIX launcher format")
def test_write_launchers_posix(tmp_path):
    mcp_dir = tmp_path / "mcp-servers"
    mcp_dir.mkdir()
    _make_server(mcp_dir, "netcdf_reader",
                 "metplot-netcdf-reader", "src.mcp.netcdf_reader.server")
    _make_server(mcp_dir, "plot_renderer",
                 "metplot-plot-renderer", "src.mcp.plot_renderer.server")

    launcher_dir = tmp_path / "bin"
    python_bin = Path("/some/venv/bin/python")
    written = write_launchers(python_bin, launcher_dir, mcp_dir)

    names = sorted(p.name for p in written)
    assert names == ["metplot-netcdf-reader", "metplot-plot-renderer"]

    for path in written:
        # Executable
        mode = path.stat().st_mode
        assert mode & stat.S_IXUSR, f"{path.name} not user-executable"
        # Shebang + python invocation
        text = path.read_text()
        assert text.startswith("#!/usr/bin/env bash")
        assert "/some/venv/bin/python" in text
        assert "-m" in text
        # Targets the right module
        if "netcdf-reader" in path.name:
            assert "src.mcp.netcdf_reader.server" in text
        else:
            assert "src.mcp.plot_renderer.server" in text


def test_write_launchers_creates_dir_if_missing(tmp_path):
    mcp_dir = tmp_path / "mcp-servers"
    mcp_dir.mkdir()
    _make_server(mcp_dir, "x", "ep-x", "src.mcp.x.server")
    launcher_dir = tmp_path / "deeply" / "nested" / "bin"
    assert not launcher_dir.exists()

    written = write_launchers(Path("/usr/bin/python3"), launcher_dir, mcp_dir)

    assert launcher_dir.is_dir()
    assert len(written) == 1


def test_write_launchers_overwrites_existing(tmp_path):
    """Re-running setup must rewrite stale launchers — each session can
    use a different Python."""
    mcp_dir = tmp_path / "mcp-servers"
    mcp_dir.mkdir()
    _make_server(mcp_dir, "x", "ep-x", "src.mcp.x.server")
    launcher_dir = tmp_path / "bin"

    write_launchers(Path("/old/python"), launcher_dir, mcp_dir)
    first = (launcher_dir / "ep-x").read_text() if os.name != "nt" \
        else (launcher_dir / "ep-x.cmd").read_text()
    assert "/old/python" in first

    write_launchers(Path("/new/python"), launcher_dir, mcp_dir)
    second = (launcher_dir / "ep-x").read_text() if os.name != "nt" \
        else (launcher_dir / "ep-x.cmd").read_text()
    assert "/new/python" in second
    assert "/old/python" not in second


def test_write_launchers_skips_dirs_without_pyproject(tmp_path):
    mcp_dir = tmp_path / "mcp-servers"
    mcp_dir.mkdir()
    _make_server(mcp_dir, "ok_pkg", "ep-ok", "src.mcp.ok.server")
    # A subdirectory missing pyproject.toml shouldn't crash
    (mcp_dir / "stale_no_pyproject").mkdir()

    written = write_launchers(Path("/usr/bin/python3"),
                              tmp_path / "bin", mcp_dir)
    assert len(written) == 1
    assert written[0].name.startswith("ep-ok")


def test_write_launchers_quotes_paths_with_spaces(tmp_path):
    """A python path with a space must not break the launcher."""
    mcp_dir = tmp_path / "mcp-servers"
    mcp_dir.mkdir()
    _make_server(mcp_dir, "x", "ep-x", "src.mcp.x.server")

    python_bin = Path("/path with space/python")
    written = write_launchers(python_bin, tmp_path / "bin", mcp_dir)

    text = written[0].read_text()
    # POSIX path is in single quotes; Windows in double quotes.
    if os.name != "nt":
        assert "'/path with space/python'" in text
    else:
        assert '"/path with space/python"' in text


def test_args_launcher_dir_default_none():
    a = parse_args([])
    assert a.launcher_dir is None


def test_args_launcher_dir_from_cli(tmp_path):
    a = parse_args(["--launcher-dir", str(tmp_path / "bin")])
    assert a.launcher_dir == tmp_path / "bin"

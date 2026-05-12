# tests/targets/claude_code/test_mcp_smoke.py
"""Smoke test: bundled MCP servers can be imported and list their tools.

Verifies the re-rooted-source strategy (§3.1 of the spec) actually
resolves imports. Doesn't run the stdio MCP loop — that's covered by
cycle 1+2's own tests.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path
from typing import TypedDict

import pytest


class _Server(TypedDict):
    package_dir: str
    expected_tool_count: int


_SERVERS: list[_Server] = [
    {"package_dir": "netcdf_reader", "expected_tool_count": 10},
    {"package_dir": "plot_renderer", "expected_tool_count": 3},
]


def _evict_src_modules() -> None:
    """Drop any cached src.* modules so a subsequent import is forced to
    re-resolve via the current sys.path."""
    for m in [m for m in sys.modules if m == "src" or m.startswith("src.")]:
        del sys.modules[m]


@pytest.mark.parametrize("server", _SERVERS,
                         ids=lambda s: s["package_dir"])
def test_bundled_server_imports(built_plugin: Path, server: _Server) -> None:
    """Verify the bundle's own source answers `from src.mcp.<pkg>...`.

    Why the precaution: the canonical repo's `src/` is already on
    sys.path during pytest, so a sloppier test would silently resolve
    via the canonical path even when the bundle is broken (the cycle-6
    pyproject regression hid behind exactly that). To force the bundle
    to answer, we put `<bundle>/` (NOT `<bundle>/src/`) at sys.path[0]
    and evict any cached `src.*` modules, then assert that the resolved
    server module's file lives inside the bundle.
    """
    bundle_root = built_plugin / "mcp-servers" / server["package_dir"]
    sys.path.insert(0, str(bundle_root))
    _evict_src_modules()
    try:
        modname = f"src.mcp.{server['package_dir']}.server"
        mod = importlib.import_module(modname)
        # Strongest assertion: the resolved source file came from the
        # bundle, not the canonical repo or a stale install.
        assert mod.__file__ is not None, (
            f"resolved module {modname} has no __file__ attr — that "
            f"shouldn't happen for a file-backed import")
        mod_file = Path(mod.__file__).resolve()
        assert bundle_root.resolve() in mod_file.parents, (
            f"{server['package_dir']}: imported {mod_file}, expected a path "
            f"under bundle {bundle_root}")
        names = mod.list_tool_names()
        assert isinstance(names, list)
        assert len(names) == server["expected_tool_count"], (
            f"{server['package_dir']}: expected {server['expected_tool_count']} "
            f"tools, got {len(names)}")
    finally:
        if str(bundle_root) in sys.path:
            sys.path.remove(str(bundle_root))
        _evict_src_modules()


def test_pyproject_install_metadata_complete(built_plugin: Path) -> None:
    """Verify each bundled pyproject.toml has the metadata pip needs."""
    for server in _SERVERS:
        pp_text = (built_plugin / "mcp-servers" / server["package_dir"]
                    / "pyproject.toml").read_text()
        # Key fields a pip install needs
        assert "[project]" in pp_text
        assert "name = " in pp_text
        assert "version = " in pp_text
        # Setuptools packaging block we patched in
        assert "[tool.setuptools.packages.find]" in pp_text
        assert 'include = ["src", "src.*"]' in pp_text

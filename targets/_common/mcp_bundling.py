# targets/_common/mcp_bundling.py
"""Shared MCP server bundling helper used by every build target.

Re-roots the canonical `src/mcp/<name>/` source under
`<dst_root>/<name>/src/mcp/<name>/` so the `from src.mcp.<name>...`
import path used in server.py continues to work after `pip install`
from the bundled location. Patches pyproject.toml to enable
setuptools.packages.find against the bundled `src/` directory.

The patched `[tool.setuptools.packages.find]` uses
`include = ["src", "src.*"]` (with `namespaces = true`) so that
`src` is preserved as a namespace prefix in the installed wheel.
Using `where = ["src"]` would strip the prefix and break the
`from src.mcp.<name>...` imports the canonical source uses.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


MCP_SERVERS = [
    {
        "package_dir": "netcdf_reader",
        "external_name": "netcdf-reader",
        "entry_point": "metplot-netcdf-reader",
    },
    {
        "package_dir": "plot_renderer",
        "external_name": "plot-renderer",
        "entry_point": "metplot-plot-renderer",
    },
]


def bundle_mcp_servers(src_root: Path, dst_root: Path) -> list[dict[str, Any]]:
    """Bundle each MCP server into `dst_root/<package_dir>/`.

    Returns the MCP_SERVERS list (passed through, for symmetry with
    callers that want a single function to both bundle and discover).
    """
    dst_root.mkdir(parents=True, exist_ok=True)
    for server in MCP_SERVERS:
        pkg_dir = server["package_dir"]
        src = src_root / "mcp" / pkg_dir
        if not src.is_dir():
            raise RuntimeError(f"missing MCP server source: {src}")
        dst = dst_root / pkg_dir
        dst.mkdir()

        # Re-root: <dst>/src/mcp/<pkg_dir>/ ← copy of <src>/
        bundled_src = dst / "src" / "mcp" / pkg_dir
        bundled_src.parent.mkdir(parents=True)
        shutil.copytree(src, bundled_src)

        # Patch pyproject.toml
        pyproject_text = (src / "pyproject.toml").read_text()
        if "[tool.setuptools.packages.find]" not in pyproject_text:
            pyproject_text += (
                "\n[tool.setuptools.packages.find]\n"
                'include = ["src", "src.*"]\n'
                "namespaces = true\n"
            )
        (dst / "pyproject.toml").write_text(pyproject_text)

        # Carry README.md if present
        readme = src / "README.md"
        if readme.exists():
            shutil.copy2(readme, dst / "README.md")

    return list(MCP_SERVERS)

# tests/tools/test_install_deps_real.py
"""Optional real-install integration. Gated on METPLOT_REAL_INSTALL=1.

Creates a fresh venv, runs the actual installer, asserts the
entry-point scripts become callable.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


pytestmark = pytest.mark.skipif(
    os.environ.get("METPLOT_REAL_INSTALL") != "1",
    reason="set METPLOT_REAL_INSTALL=1 to enable real-install tests",
)


def _make_venv(tmp_path: Path) -> Path:
    venv_dir = tmp_path / "v"
    subprocess.run([sys.executable, "-m", "venv", str(venv_dir)],
                    check=True)
    return venv_dir


def test_minimum_install_runs_without_optionals(tmp_path):
    """--no-cartopy --no-scipy: just the two MCP servers."""
    venv = _make_venv(tmp_path)
    env = os.environ.copy()
    env["VIRTUAL_ENV"] = str(venv)
    result = subprocess.run(
        [sys.executable, "-m", "tools.install_deps",
         "--no-cartopy", "--no-scipy",
         "--mcp-servers-dir", str(REPO_ROOT / "src" / "mcp")],
        cwd=REPO_ROOT, env=env, check=False, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr

    # Verify entry-point scripts exist in the venv
    nc = venv / "bin" / "metplot-netcdf-reader"
    pr = venv / "bin" / "metplot-plot-renderer"
    assert nc.is_file(), f"missing entry point: {nc}"
    assert pr.is_file(), f"missing entry point: {pr}"

# tests/mcp/plot_renderer/integration/test_real_files.py
"""Optional real-files integration. Gated on `NCPLOT_REAL_FILES=1`.

Reads paths from tests/integration/real_files.json (gitignored) and
drives each render tool against actual files. See REAL_FILES_SETUP.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.mcp.plot_renderer.tools import render_map as rm
from src.mcp.plot_renderer.tools.render_profile import render_profile
from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries

CONFIG = Path(__file__).resolve().parents[3] / "integration" / "real_files.json"

pytestmark = pytest.mark.skipif(
    os.environ.get("NCPLOT_REAL_FILES") != "1",
    reason="set NCPLOT_REAL_FILES=1 to enable real-files tests",
)


def _config() -> dict:
    if not CONFIG.exists():
        pytest.skip(f"missing config {CONFIG}")
    return json.loads(CONFIG.read_text())


def test_real_cf_slice_renders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config()
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed")
    spec = {"slice_ref": {"path": cfg["cf_slice"], "format": "netcdf",
                            "variable": cfg["variable_cf"]},
            "output_path": str(tmp_path / "cf.png"),
            "title": "real CF"}
    env = rm.render_map(spec)
    assert env["ok"] is True, env.get("error")
    assert Path(env["result"]["output_path"]).stat().st_size > 50_000
    assert env["result"]["nan_fraction"] < 1.0

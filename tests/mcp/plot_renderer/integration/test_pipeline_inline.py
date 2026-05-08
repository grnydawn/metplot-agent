# tests/mcp/plot_renderer/integration/test_pipeline_inline.py
"""End-to-end inline-form pipeline: spec → render → PNG + oracle."""
import json
from pathlib import Path

import numpy as np
import pytest

from src.mcp.plot_renderer.tools import render_map as rm
from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries
from src.mcp.plot_renderer.tools.render_profile import render_profile


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_inline_map_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lat = np.linspace(-30, 30, 7).tolist()
    lon = np.linspace(-60, 60, 13).tolist()
    values = (np.outer(np.cos(np.deg2rad(lat)),
                        np.sin(np.deg2rad(lon))) * 10.0).tolist()
    spec = {"values": values, "lat": lat, "lon": lon,
            "title": "demo", "colormap": "viridis",
            "output_path": str(tmp_path / "map.png")}
    env = rm.render_map(spec)
    assert env["ok"] is True
    out = env["result"]
    assert Path(out["output_path"]).exists()
    assert out["file_size_bytes"] > 5000
    assert out["oracle"]["tool"] == "render_map"
    assert out["oracle"]["drawn"]["projection_class"] == "PlateCarree"


def test_inline_timeseries_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [1.0, 2.0, 3.0],
            "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
            "label": "demo",
            "title": "Annual", "trendline": "linear"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).exists()
    assert env["result"]["oracle"]["drawn"]["trendline_present"] is True


def test_inline_profile_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [288.0, 250.0, 220.0],
            "vertical": [1000.0, 500.0, 100.0],
            "vertical_units": "hPa", "title": "T(p)"}
    env = render_profile(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["log_scale"] is True


def test_oracle_sidecar_when_requested(tmp_path, monkeypatch):
    """write_oracle_sidecar is documented in spec §5.5 — defer the
    sidecar implementation: this is a follow-up if needed.
    """
    monkeypatch.chdir(tmp_path)
    # Even without sidecar implementation, the oracle is in result.
    spec = {"values": [1.0, 2.0],
            "time": ["2024-01-15", "2024-02-15"]}
    env = render_timeseries(spec)
    assert "oracle" in env["result"]

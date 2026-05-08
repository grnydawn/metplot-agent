# tests/mcp/plot_renderer/integration/test_three_tools_smoke.py
"""Smoke: each callable tool produces a non-empty figure."""
import os
from pathlib import Path

import pytest

from src.mcp.plot_renderer.server import dispatch
from src.mcp.plot_renderer.tools import render_map as rm


def test_smoke_timeseries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_timeseries", {"spec": {
        "values": [1.0, 2.0, 3.0],
        "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
        "label": "x",
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 1000


def test_smoke_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_profile", {"spec": {
        "values": [288.0, 250.0],
        "vertical": [1000.0, 500.0],
        "vertical_units": "hPa",
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 1000


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_smoke_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_map", {"spec": {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [0.0, 1.0],
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 5000

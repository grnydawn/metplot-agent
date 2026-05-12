"""Cycle 13 theme D — render_section pcolormesh.

Pcolormesh of values [n_samples, n_levels] against
distances_km × vertical_coord. Vertical axis inverted by
default when vertical_units indicate depth-down semantics
(m, depth_m, Pa, hPa).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

from src.mcp.plot_renderer.tools.render_section import render_section


def test_basic_section_renders_png(tmp_path: Path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    n_samples, n_levels = 50, 12
    values = np.linspace(0, 30, n_samples * n_levels).reshape(
        n_samples, n_levels)
    distances = np.linspace(0, 5000, n_samples)
    vertical = np.linspace(0, 1000, n_levels)
    env = render_section({
        "values": values.tolist(),
        "distances_km": distances.tolist(),
        "vertical_coord": vertical.tolist(),
        "vertical_units": "m",
        "title": "test cross-section",
    })
    assert env["ok"] is True, env.get("error")
    out_path = Path(env["result"]["output_path"])
    assert out_path.exists()
    assert out_path.stat().st_size > 5_000
    assert env["result"]["shape"] == [n_samples, n_levels]
    drawn = env["result"]["oracle"]["drawn"]
    assert drawn["n_samples"] == n_samples
    assert drawn["n_levels"] == n_levels
    assert drawn["invert_vertical"] is True  # m → depth-down


def test_invert_vertical_off_for_height_units(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_section({
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "distances_km": [0.0, 100.0],
        "vertical_coord": [0.0, 1000.0],
        "vertical_units": "km",  # not in depth-down set
    })
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["invert_vertical"] is False


def test_pressure_units_triggers_invert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_section({
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "distances_km": [0.0, 100.0],
        "vertical_coord": [1000.0, 100.0],
        "vertical_units": "hPa",
    })
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["invert_vertical"] is True


def test_shape_mismatch_distances(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_section({
        "values": [[1.0, 2.0], [3.0, 4.0]],  # n_samples=2
        "distances_km": [0.0, 1.0, 2.0],     # length 3
        "vertical_coord": [0.0, 1.0],
    })
    assert env["ok"] is False
    assert env["error"]["code"] == "shape_mismatch"


def test_shape_mismatch_vertical(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_section({
        "values": [[1.0, 2.0], [3.0, 4.0]],  # n_levels=2
        "distances_km": [0.0, 1.0],
        "vertical_coord": [0.0, 1.0, 2.0],   # length 3
    })
    assert env["ok"] is False
    assert env["error"]["code"] == "shape_mismatch"


def test_missing_fields_returns_invalid_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_section({"values": [[1.0]]})
    assert env["ok"] is False
    assert env["error"]["code"] == "invalid_spec"


def test_explicit_invert_override(tmp_path, monkeypatch):
    """invert_vertical=False overrides the depth-down default."""
    monkeypatch.chdir(tmp_path)
    env = render_section({
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "distances_km": [0.0, 100.0],
        "vertical_coord": [0.0, 1000.0],
        "vertical_units": "m",
        "invert_vertical": False,  # override
    })
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["invert_vertical"] is False


def test_server_dispatch_routes_render_section():
    """Cycle 13: server.list_tool_names() exposes render_section
    and dispatch routes to it."""
    from src.mcp.plot_renderer.server import dispatch, list_tool_names
    assert "render_section" in list_tool_names()
    out = dispatch("render_section", {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "distances_km": [0.0, 100.0],
        "vertical_coord": [0.0, 1.0],
    })
    assert out["ok"] is True, out.get("error")

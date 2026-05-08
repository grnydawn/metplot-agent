# tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py
import json
from pathlib import Path

from src.mcp.plot_renderer.lifecycle import (
    resolve_output_path, auto_name,
    OutputPathInvalid, FormatExtensionMismatch,
)


def test_explicit_absolute_path(tmp_path):
    target = tmp_path / "out.png"
    p = resolve_output_path(str(target), fmt="png")
    assert Path(p) == target


def test_explicit_relative_resolves_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = resolve_output_path("rel/out.png", fmt="png")
    assert Path(p).is_absolute()
    assert Path(p).name == "out.png"


def test_explicit_format_extension_mismatch(tmp_path):
    target = tmp_path / "out.png"
    try:
        resolve_output_path(str(target), fmt="pdf")
    except FormatExtensionMismatch:
        return
    raise AssertionError("expected FormatExtensionMismatch")


def test_explicit_format_inferred_from_extension(tmp_path):
    target = tmp_path / "out.svg"
    p = resolve_output_path(str(target), fmt=None)
    assert p.endswith(".svg")


def test_auto_name_basic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="map", spec={"variable": "tos",
                                     "title": "SST",
                                     "values": [[1.0]],
                                     "lat": [0.0], "lon": [0.0]},
                  fmt="png")
    assert ".ncplot/figures/" in p
    assert p.endswith(".png")
    assert "map_tos_" in p


def test_auto_name_uses_title_slug_when_no_variable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="timeseries",
                  spec={"title": "Annual Mean", "series": []},
                  fmt="pdf")
    assert "timeseries_annual-mean_" in p
    assert p.endswith(".pdf")


def test_auto_name_falls_back_to_plot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="profile", spec={}, fmt="png")
    assert "profile_plot_" in p


def test_auto_name_hash_disambiguates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p1 = auto_name(tool="map",
                   spec={"variable": "v", "values": [[1.0]],
                         "lat": [0.0], "lon": [0.0],
                         "colormap": "viridis"},
                   fmt="png")
    p2 = auto_name(tool="map",
                   spec={"variable": "v", "values": [[1.0]],
                         "lat": [0.0], "lon": [0.0],
                         "colormap": "magma"},
                   fmt="png")
    assert p1 != p2  # different specs → different hashes

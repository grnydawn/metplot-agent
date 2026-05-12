import pytest

from src.mcp.plot_renderer.tools import render_map as rm

if not rm._CARTOPY_OK:  # pragma: no cover
    pytest.skip("cartopy not installed; run map tests in maps-extra env",
                allow_module_level=True)


def test_basic_map_renders(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "title": "demo",
        "colormap": "viridis",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    out = env["result"]
    assert out["output_path"].endswith(".png")
    assert out["file_size_bytes"] > 5000
    drawn = out["oracle"]["drawn"]
    assert drawn["projection_class"] == "PlateCarree"
    assert drawn["coastlines_drawn"] is True
    assert drawn["title"] == "demo"


def test_explicit_projection_robinson(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "projection": "Robinson",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["projection_class"] == "Robinson"


def test_unknown_projection_returns_ambiguity(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "projection": "NotARealProjection",
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "unknown_projection"


def test_unknown_colormap_returns_ambiguity(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "colormap": "NotARealCmap",
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "unknown_colormap"


def test_lon_shift_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Need >=2 lats: cartopy 0.25's GEOS rejects degenerate single-row
    # geometries with "getX called on empty Point". The lon-shift logic
    # being exercised here doesn't depend on the lat axis.
    spec = {
        "values": [[1.0, 2.0, 3.0, 4.0], [5.0, 6.0, 7.0, 8.0]],
        "lat": [0.0, 1.0],
        "lon": [180.0, 270.0, 0.0, 90.0],   # 0..360 layout
        "lon_convention": "-180..180",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    codes = [w["code"] for w in env["warnings"]]
    assert "lon_shift_applied" in codes


def test_all_nan_returns_ambiguity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {
        "values": [["NaN", "NaN"], ["NaN", "NaN"]],
        "lat": [0.0, 1.0],
        "lon": [0.0, 1.0],
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "all_nan"

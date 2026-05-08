from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries


def test_single_series_sugar(tmp_path, monkeypatch, small_timeseries):
    monkeypatch.chdir(tmp_path)
    spec = {**small_timeseries,
            "title": "Demo", "ylabel": "v", "xlabel": "Year"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    out = env["result"]
    assert out["output_path"].endswith(".png")
    assert out["file_size_bytes"] > 1000
    assert out["series_count"] == 1
    assert out["oracle"]["drawn"]["title"] == "Demo"
    assert out["oracle"]["drawn"]["series_count"] == 1


def test_multi_series_legend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [1.0, 2.0],
         "time": ["2024-01-15", "2024-02-15"], "label": "A"},
        {"values": [2.0, 3.0],
         "time": ["2024-01-15", "2024-02-15"], "label": "B"},
    ], "title": "Multi"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert env["result"]["series_count"] == 2
    assert env["result"]["oracle"]["drawn"]["legend_present"] is True


def test_invalid_spec_returns_error_envelope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_timeseries({})
    assert env["ok"] is False
    assert env["error"]["code"] == "invalid_spec"


def test_color_cycle_warning_when_over_10_series(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [float(i)], "time": ["2024-01-15"], "label": f"S{i}"}
        for i in range(11)
    ]}
    env = render_timeseries(spec)
    assert env["ok"] is True
    codes = [w["code"] for w in env["warnings"]]
    assert "color_cycle_exceeded" in codes


def test_linear_trendline(tmp_path, monkeypatch, small_timeseries):
    monkeypatch.chdir(tmp_path)
    spec = {**small_timeseries, "trendline": "linear"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["trendline_present"] is True
    assert env["result"]["oracle"]["drawn"]["trendline_kind"] == "linear"


def test_lowess_without_scipy_returns_error(monkeypatch, tmp_path, small_timeseries):
    monkeypatch.chdir(tmp_path)
    # Force the scipy import path to fail.
    import sys
    monkeypatch.setitem(sys.modules, "scipy", None)
    monkeypatch.setitem(sys.modules, "scipy.signal", None)
    spec = {**small_timeseries, "trendline": "lowess"}
    env = render_timeseries(spec)
    assert env["ok"] is False
    assert env["error"]["code"] == "trendline_dependency_missing"

from src.mcp.plot_renderer.tools.render_profile import render_profile


def test_single_profile_pressure_log_invert(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "title": "T-profile", "xlabel": "T (K)"}
    env = render_profile(spec)
    assert env["ok"] is True
    drawn = env["result"]["oracle"]["drawn"]
    assert drawn["log_scale"] is True       # default for hPa
    assert drawn["invert_pressure"] is True
    assert drawn["vertical_axis"] == "y"
    assert drawn["title"] == "T-profile"
    assert env["result"]["series_count"] == 1


def test_meter_units_no_log_no_invert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [288.0, 270.0, 250.0],
            "vertical": [0.0, 5000.0, 10000.0],
            "vertical_units": "m"}
    env = render_profile(spec)
    drawn = env["result"]["oracle"]["drawn"]
    assert drawn["log_scale"] is False
    assert drawn["invert_pressure"] is False


def test_multi_series_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [288.0, 250.0], "vertical": [1000.0, 500.0], "label": "A"},
        {"values": [285.0, 248.0], "vertical": [1000.0, 500.0], "label": "B"},
    ], "vertical_units": "hPa"}
    env = render_profile(spec)
    assert env["ok"] is True
    assert env["result"]["series_count"] == 2
    assert env["result"]["oracle"]["drawn"]["legend_present"] is True


def test_explicit_log_false_overrides_pressure_default(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "log_scale": False}
    env = render_profile(spec)
    assert env["result"]["oracle"]["drawn"]["log_scale"] is False


def test_explicit_invert_false(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "invert_pressure": False}
    env = render_profile(spec)
    assert env["result"]["oracle"]["drawn"]["invert_pressure"] is False

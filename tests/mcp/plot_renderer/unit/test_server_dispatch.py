# tests/mcp/plot_renderer/unit/test_server_dispatch.py
from src.mcp.plot_renderer.server import dispatch, list_tool_names


def test_list_tool_names():
    assert list_tool_names() == ["render_map", "render_timeseries", "render_profile"]


def test_dispatch_unknown_tool():
    env = dispatch("not_a_tool", {})
    assert env["ok"] is False
    assert env["error"]["code"] == "unknown_tool"


def test_dispatch_render_timeseries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = {"spec": {"values": [0.0, 1.0],
                      "time": ["2024-01-15", "2024-02-15"],
                      "label": "demo"}}
    env = dispatch("render_timeseries", args)
    assert env["ok"] is True


def test_dispatch_bad_args_returns_internal_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Missing 'spec' key — render_timeseries(spec) gets called with arg
    env = dispatch("render_timeseries", {"wrong": True})
    assert env["ok"] is False
    # Either "internal_render_error" (caught in render_*) or "invalid_spec".
    assert env["error"]["code"] in ("internal_render_error", "invalid_spec")

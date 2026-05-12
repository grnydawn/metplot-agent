from src.mcp.netcdf_reader.server import dispatch, list_tool_names


def test_list_tool_names_exposes_all_10():
    names = set(list_tool_names())
    assert names == {
        "inspect", "resolve_spec", "regrid_to_centers",
        "peek", "read_slice", "compute_stats",
        "find_variables", "find_time",
        # Cycle 11 — unstructured-mesh helpers
        "find_nearest_cell", "cells_in_bbox",
    }


def test_dispatch_inspect_returns_envelope(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = dispatch("inspect", {"path": str(cf_3d_file)})
    assert out["ok"] is True
    assert "convention" in out["result"]


def test_dispatch_unknown_tool_returns_error():
    out = dispatch("not_a_tool", {})
    assert out["ok"] is False
    assert "unknown" in out["error"]["message"].lower()


def test_dispatch_resolve_spec(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = dispatch("resolve_spec", {
        "path": str(cf_4d_file), "variable": "ta",
        "time": "2024-09-01T06:00",
    })
    assert out["ok"] is True
    assert out["result"]["variable"] == "ta"


def test_dispatch_find_variables(cf_4d_file):
    out = dispatch("find_variables", {
        "path": str(cf_4d_file), "hint": "temperature",
    })
    assert out["ok"] is True
    assert out["result"]["matches"][0]["name"] == "ta"

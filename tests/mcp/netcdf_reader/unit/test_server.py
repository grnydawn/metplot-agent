from src.mcp.netcdf_reader.server import dispatch, list_tool_names


def test_list_tool_names_exposes_all_14():
    names = set(list_tool_names())
    assert names == {
        "inspect", "resolve_spec", "regrid_to_centers",
        "peek", "read_slice", "compute_stats",
        "find_variables", "find_time",
        # Cycle 11 — unstructured-mesh helpers
        "find_nearest_cell", "cells_in_bbox",
        # Cycle 12 — ncks-parity analysis tools
        "reduce_variable", "dump_cdl",
        # Cycle 13 — region lookup (theme C) +
        # great-circle cross-section sampler (theme D).
        "find_region", "slice_along_section",
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


def test_dispatch_reduce_variable(cf_3d_file):
    """Cycle 12: dispatch routes reduce_variable to its tool."""
    out = dispatch("reduce_variable", {
        "path": str(cf_3d_file), "variable": "tos",
        "reduce_dims": ["time"], "op": "avg",
    })
    assert out["ok"] is True, out.get("error")
    assert out["result"]["op"] == "avg"
    assert out["result"]["reduced_dims"] == ["time"]


def test_dispatch_dump_cdl(cf_3d_file):
    """Cycle 12: dispatch routes dump_cdl to its tool."""
    out = dispatch("dump_cdl", {
        "path": str(cf_3d_file), "header_only": True,
    })
    assert out["ok"] is True, out.get("error")
    cdl = out["result"]["cdl"]
    assert cdl.startswith("netcdf ")
    assert "dimensions:" in cdl
    assert "data:" not in cdl  # header_only

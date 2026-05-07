# tests/mcp/netcdf_reader/unit/test_resolve_spec.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def test_resolve_spec_exact_time(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T06:00:00",
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is True
    r = env["result"]
    assert r["variable"] == "ta"
    assert r["resolved"]["time_match"] == "exact"
    assert r["resolved"]["time_index"] == 1


def test_resolve_spec_nearest_time_returns_match_kind(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T07:00:00",  # not exact — nearest is 06:00
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert r["resolved"]["time_match"] in ("nearest", "previous")


def test_resolve_spec_unknown_variable_returns_ambiguous(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="not_a_var",
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "variable"
    assert len(env["error"]["candidates"]) >= 1


def test_resolve_spec_lat_lon_bbox(cf_3d_file):
    env = resolve_spec(
        str(cf_3d_file), variable="tos",
        lat=[20, 50], lon=[100, 200],
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert "lat_indices" in r["resolved"]
    assert "lon_indices" in r["resolved"]
    assert r["slice_shape"][0] >= 1


def test_resolve_spec_level_on_3d_returns_not_4d(cf_3d_file):
    env = resolve_spec(
        str(cf_3d_file), variable="tos",
        level=500,
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "not_4d"


def test_resolve_spec_estimates_bytes(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T00",
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert r["estimated_bytes"] > 0
    assert r["slice_shape"][0] == 1  # one time step

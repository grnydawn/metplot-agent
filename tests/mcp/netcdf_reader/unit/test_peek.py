from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.peek import peek, PEEK_HARD_CAP_BYTES


def test_peek_single_point(cf_3d_file):
    env = peek(str(cf_3d_file), variable="tos",
               time="2024-09-01", lat=10.0, lon=100.0,
               adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert "value" in r
    assert isinstance(r["value"], (int, float, str))
    assert r["units"] == "K"
    assert "distance_to_nearest" in r
    assert "lat_deg" in r["distance_to_nearest"]


def test_peek_refuses_when_exceeds_cap(cf_3d_file):
    # Whole-grid peek would exceed cap
    env = peek(str(cf_3d_file), variable="tos",
               time="2024-09-01",
               adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] == "size_limit_exceeded"
    assert env["error"]["context"]["cap"] == PEEK_HARD_CAP_BYTES

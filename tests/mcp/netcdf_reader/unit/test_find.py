# tests/mcp/netcdf_reader/unit/test_find.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.find import find_variables, find_time


def test_find_variables_long_name(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="temperature",
                         adapter=NetCDFAdapter())
    r = env["result"]
    assert len(r["matches"]) >= 1
    top = r["matches"][0]
    assert top["name"] == "ta"
    assert top["matched_field"] == "long_name"
    assert top["score"] > 0.0


def test_find_variables_standard_name(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="air_temperature",
                         adapter=NetCDFAdapter())
    top = env["result"]["matches"][0]
    assert top["name"] == "ta"
    assert top["matched_field"] == "standard_name"


def test_find_variables_unrelated_hint_returns_low_scores(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="quokka",
                         adapter=NetCDFAdapter())
    matches = env["result"]["matches"]
    if matches:
        assert matches[0]["score"] < 0.5


def test_find_time_exact(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="2024-09-01T06:00",
                    adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["match_kind"] == "exact"
    assert r["matches"][0]["index"] == 1


def test_find_time_first(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="first", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["index"] == 0


def test_find_time_last(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="last", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["index"] == 2


def test_find_time_partial(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="2024-09-01",
                    adapter=NetCDFAdapter())
    r = env["result"]
    assert len(r["matches"]) >= 1

"""CDL parser — minimal subset for ncdump -h output."""
from __future__ import annotations

import pytest

from src.mcp.netcdf_reader.cdl_parser import CDLParseError, parse_cdl


# Minimal real-world-shaped CDL header (from ncdump -h)
_CDL_REAL = """netcdf example {
dimensions:
    time = UNLIMITED ; // (12 currently)
    lat = 73 ;
    lon = 144 ;
variables:
    double time(time) ;
        time:units = "days since 1990-1-1 0:0:0" ;
        time:long_name = "Time" ;
    double lat(lat) ;
        lat:units = "degrees_north" ;
    double lon(lon) ;
        lon:units = "degrees_east" ;
    float t2m(time, lat, lon) ;
        t2m:units = "K" ;
        t2m:long_name = "2m air temperature" ;
        t2m:_FillValue = 9.96921e+36f ;

// global attributes:
        :Conventions = "CF-1.8" ;
        :history = "Created 2026-01-01" ;
}
"""


def test_parse_header_filename():
    r = parse_cdl(_CDL_REAL)
    assert r["name"] == "example"


def test_parse_dimensions():
    r = parse_cdl(_CDL_REAL)
    dims = {d["name"]: d for d in r["dimensions"]}
    assert dims["time"]["unlimited"] is True
    assert dims["time"]["size"] is None
    assert dims["lat"]["size"] == 73
    assert dims["lat"]["unlimited"] is False
    assert dims["lon"]["size"] == 144


def test_parse_variables_names_and_types():
    r = parse_cdl(_CDL_REAL)
    names = [v["name"] for v in r["variables"]]
    assert names == ["time", "lat", "lon", "t2m"]
    types = {v["name"]: v["type"] for v in r["variables"]}
    assert types["t2m"] == "float"
    assert types["time"] == "double"


def test_parse_variable_dims():
    r = parse_cdl(_CDL_REAL)
    by_name = {v["name"]: v for v in r["variables"]}
    assert by_name["t2m"]["dim_names"] == ["time", "lat", "lon"]
    assert by_name["time"]["dim_names"] == ["time"]


def test_parse_variable_attrs():
    r = parse_cdl(_CDL_REAL)
    by_name = {v["name"]: v for v in r["variables"]}
    assert by_name["t2m"]["attrs"]["units"] == "K"
    assert by_name["t2m"]["attrs"]["long_name"] == "2m air temperature"


def test_parse_global_attrs():
    r = parse_cdl(_CDL_REAL)
    assert r["global_attrs"]["Conventions"] == "CF-1.8"
    assert "Created 2026-01-01" in r["global_attrs"]["history"]


def test_parse_empty_raises():
    with pytest.raises(CDLParseError):
        parse_cdl("")


def test_parse_no_header_raises():
    with pytest.raises(CDLParseError):
        parse_cdl("this is not cdl\nat all\n")


def test_parse_stub_minimal_works():
    """Stub from the in-proc sshd has empty dimensions/variables blocks."""
    stub = "netcdf foo {\n  dimensions:\n  variables:\n}\n"
    r = parse_cdl(stub)
    assert r["name"] == "foo"
    assert r["dimensions"] == []
    assert r["variables"] == []

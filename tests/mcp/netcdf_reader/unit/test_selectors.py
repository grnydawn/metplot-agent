import pytest
from src.mcp.netcdf_reader.selectors import (
    parse_time, parse_level, parse_latlon,
    TimeSelector, LevelSelector, LatLonSelector,
    SelectorError,
)


def test_parse_time_iso_string():
    sel = parse_time("2024-09-15")
    assert isinstance(sel, TimeSelector)
    assert sel.kind == "iso"
    assert sel.value == "2024-09-15"


def test_parse_time_range():
    sel = parse_time(["2024-01", "2024-12"])
    assert sel.kind == "range"
    assert sel.value == ["2024-01", "2024-12"]


def test_parse_time_index():
    sel = parse_time({"index": 5})
    assert sel.kind == "index"
    assert sel.value == 5


def test_parse_time_index_list():
    sel = parse_time({"index": [0, 6, 12]})
    assert sel.kind == "index_list"
    assert sel.value == [0, 6, 12]


def test_parse_time_sentinel():
    assert parse_time("first").kind == "sentinel"
    assert parse_time("first").value == "first"
    assert parse_time("last").value == "last"


def test_parse_time_invalid():
    with pytest.raises(SelectorError):
        parse_time(42.5)


def test_parse_level_numeric():
    sel = parse_level(500)
    assert sel.kind == "numeric"
    assert sel.value == 500


def test_parse_level_list():
    sel = parse_level([500, 850, 1000])
    assert sel.kind == "list"
    assert sel.value == [500, 850, 1000]


def test_parse_level_sentinel():
    assert parse_level("surface").value == "surface"
    assert parse_level("top").value == "top"


def test_parse_latlon_bbox():
    sel = parse_latlon([20, 70])
    assert sel.kind == "bbox"
    assert sel.value == [20, 70]


def test_parse_latlon_point():
    sel = parse_latlon(42.3)
    assert sel.kind == "point"
    assert sel.value == 42.3


def test_parse_latlon_index():
    sel = parse_latlon({"index": [0, 100]})
    assert sel.kind == "index"
    assert sel.value == [0, 100]

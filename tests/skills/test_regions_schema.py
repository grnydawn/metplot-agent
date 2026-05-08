# tests/skills/test_regions_schema.py
import json
from pathlib import Path

import pytest


_REGIONS_PATH = (Path(__file__).resolve().parents[2]
                 / "src" / "skills" / "netcdf-plot-map"
                 / "references" / "regions.json")


def _load() -> dict:
    return json.loads(_REGIONS_PATH.read_text())


def test_file_parses():
    d = _load()
    assert isinstance(d, dict)


def test_schema_version_pinned():
    d = _load()
    assert d["schema_version"] == 1


def test_regions_dict_present():
    d = _load()
    assert isinstance(d["regions"], dict)
    assert len(d["regions"]) > 0


def test_categories_consistent():
    d = _load()
    valid_categories = set(d["categories"])
    for name, region in d["regions"].items():
        assert region.get("category") in valid_categories, (
            f"region {name!r} has unknown category {region.get('category')!r}")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_region_has_required_fields(region_name: str, region: dict):
    for field in ("lon_min", "lon_max", "lat_min", "lat_max"):
        assert field in region, f"region {region_name!r} missing {field}"
        assert isinstance(region[field], (int, float)), (
            f"region {region_name!r} {field} must be numeric")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_lat_range_sane(region_name: str, region: dict):
    assert -90 <= region["lat_min"] <= 90
    assert -90 <= region["lat_max"] <= 90
    assert region["lat_min"] <= region["lat_max"], (
        f"region {region_name!r} lat_min > lat_max")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_lon_range_sane(region_name: str, region: dict):
    # Allow lon_min > lon_max for regions that cross the dateline
    assert -180 <= region["lon_min"] <= 180
    assert -180 <= region["lon_max"] <= 180

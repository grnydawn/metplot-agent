# tests/skills/test_regions_sync.py
"""Verify regions.md table entries match regions.json entries."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGIONS_DIR = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
                / "references")
_REGIONS_MD = _REGIONS_DIR / "regions.md"
_REGIONS_JSON = _REGIONS_DIR / "regions.json"

# Regex to parse markdown table rows like:
# | North Atlantic      |     -80 |       0 |      20 |      70 |
_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
)


def _parse_md_regions() -> dict[str, tuple[float, float, float, float]]:
    out: dict[str, tuple[float, float, float, float]] = {}
    for line in _REGIONS_MD.read_text().splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        # Skip header rows
        if name in ("Name", "----"):
            continue
        # Skip header separator rows like '---'
        if all(c in "-: " for c in name):
            continue
        try:
            lon_min, lon_max, lat_min, lat_max = (float(m.group(i)) for i in range(2, 6))
        except ValueError:
            continue
        out[name] = (lon_min, lon_max, lat_min, lat_max)
    return out


def _load_json_regions() -> dict[str, tuple[float, float, float, float]]:
    d = json.loads(_REGIONS_JSON.read_text())
    return {name: (r["lon_min"], r["lon_max"], r["lat_min"], r["lat_max"])
            for name, r in d["regions"].items()}


def test_md_and_json_have_same_region_names():
    md = set(_parse_md_regions())
    js = set(_load_json_regions())
    only_in_md = md - js
    only_in_json = js - md
    assert not only_in_md, f"in regions.md but not regions.json: {sorted(only_in_md)}"
    assert not only_in_json, f"in regions.json but not regions.md: {sorted(only_in_json)}"


@pytest.mark.parametrize("name,bbox", _load_json_regions().items())
def test_each_json_region_has_matching_md_bbox(name: str, bbox: tuple) -> None:
    md = _parse_md_regions()
    if name not in md:
        pytest.skip(f"{name!r} not in regions.md (caught by other test)")
    assert md[name] == bbox, (
        f"region {name!r}: md says {md[name]}, json says {bbox}")

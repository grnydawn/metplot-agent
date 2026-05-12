"""Cycle 13 theme C — find_region tool.

find_region(name) looks up a region by case-insensitive name in
regions.json and returns its bbox dict. Unknown names produce
an ambiguous envelope with close-match candidates so the agent
can ask the user to clarify.

The regions catalog lives at
src/skills/netcdf-plot-map/references/regions.json (shared
with the map skill's region selector).
"""
from __future__ import annotations

from src.mcp.netcdf_reader.regions import find_region


def test_exact_match_returns_bbox():
    env = find_region("North Atlantic")
    assert env["ok"] is True, env.get("error")
    r = env["result"]
    assert r["name"] == "North Atlantic"
    assert r["lon_min"] == -80
    assert r["lon_max"] == 0
    assert r["lat_min"] == 20
    assert r["lat_max"] == 70
    assert r["category"] == "ocean_basin"


def test_case_insensitive_match():
    env = find_region("NORTH ATLANTIC")
    assert env["ok"] is True
    assert env["result"]["lon_min"] == -80


def test_lowercase_match():
    env = find_region("north atlantic")
    assert env["ok"] is True


def test_cross_dateline_region_preserved():
    """North Pacific spans the dateline (lon_min=120,
    lon_max=-100). The bbox is returned as-is — interpretation
    is up to the caller (cells_in_bbox treats lon_min > lon_max
    as a cross-dateline range)."""
    env = find_region("North Pacific")
    assert env["ok"] is True
    r = env["result"]
    assert r["lon_min"] == 120
    assert r["lon_max"] == -100


def test_climate_index_region():
    env = find_region("Niño 3.4")
    assert env["ok"] is True
    assert env["result"]["category"] == "climate_index"


def test_unknown_returns_ambiguous_with_candidates():
    env = find_region("North Atlantik")  # typo
    assert env["ok"] is False
    err = env["error"]
    assert err["code"] == "ambiguous"
    assert err.get("subcode") == "region"
    cands = err.get("candidates", [])
    assert len(cands) > 0
    cand_names = [c["value"] for c in cands]
    assert "North Atlantic" in cand_names


def test_unknown_no_close_match_returns_at_least_one_suggestion():
    """Even a wildly off name returns the first few region
    names so the user can see what's available."""
    env = find_region("Atlantis")
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert len(env["error"].get("candidates", [])) > 0


def test_envelope_shape():
    env = find_region("Europe")
    assert env["ok"] is True
    assert "result" in env
    for key in ("name", "lat_min", "lat_max", "lon_min", "lon_max",
                "category"):
        assert key in env["result"]

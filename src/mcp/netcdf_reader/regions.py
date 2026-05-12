# src/mcp/netcdf_reader/regions.py
"""Cycle 13 theme C — find_region(name) bbox lookup.

Looks up a region by case-insensitive name against the shared
regions.json catalog (which also drives the map skill's region
selector). Returns the bbox dict + category; ambiguous envelope
with close-match candidates when the name doesn't resolve.

Cross-dateline regions (lon_min > lon_max, e.g. North Pacific)
are returned as-is — interpretation belongs to the caller. The
cycle-11 cells_in_bbox already knows how to handle that shape.
"""
from __future__ import annotations

import difflib
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.mcp.netcdf_reader import envelope

_REGIONS_PATH = (Path(__file__).resolve().parents[3]
                  / "src" / "skills" / "netcdf-plot-map"
                  / "references" / "regions.json")


@lru_cache(maxsize=1)
def _load_regions() -> dict[str, dict[str, Any]]:
    with _REGIONS_PATH.open() as f:
        data = json.load(f)
    return data.get("regions", {})


def find_region(name: str) -> dict[str, Any]:
    """Case-insensitive lookup. Returns the bbox dict on
    success, or an ambiguous envelope with close-match
    candidates on miss."""
    regions = _load_regions()
    # Build a lower-case → canonical-name lookup for case-insens.
    lower_to_canon = {k.lower(): k for k in regions}
    key = name.lower()
    if key in lower_to_canon:
        canon = lower_to_canon[key]
        r = regions[canon]
        return envelope.success({
            "name": canon,
            "lat_min": r["lat_min"],
            "lat_max": r["lat_max"],
            "lon_min": r["lon_min"],
            "lon_max": r["lon_max"],
            "category": r.get("category"),
            "notes": r.get("notes"),
        })
    # No exact match — surface close candidates.
    close = difflib.get_close_matches(name, list(regions.keys()),
                                       n=5, cutoff=0.4)
    if not close:
        # Fall back to first 5 names so the user sees what's there.
        close = list(regions.keys())[:5]
    candidates = [{"value": c, "label": c,
                    "category": regions[c].get("category"),
                    "evidence": ["regions.json string-distance"],
                    "confidence": 0.5,
                    "param": "name", "sensitive": False}
                   for c in close]
    return envelope.ambiguous(
        "region",
        f"no region named {name!r}",
        candidates=candidates,
        prompt="Did you mean one of these regions?",
        retry_with_param="name",
        context={"requested": name},
    )


def find_region_tool(*, name: str, **_kwargs: Any) -> dict[str, Any]:
    """MCP wrapper. Adapter kwarg is accepted but ignored — the
    lookup doesn't need a NetCDF file."""
    return find_region(name)

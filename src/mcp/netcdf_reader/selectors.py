"""⤴ format-agnostic — eligible for _core/ lift.

Canonical selector parsing. Skills do natural-language translation;
this module does deterministic resolution. See spec §5.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SelectorError(ValueError):
    pass


@dataclass
class TimeSelector:
    kind: str  # "iso" | "range" | "index" | "index_list" | "sentinel"
    value: Any


@dataclass
class LevelSelector:
    kind: str  # "numeric" | "list" | "index" | "index_list" | "sentinel"
    value: Any


@dataclass
class LatLonSelector:
    kind: str  # "bbox" | "point" | "index"
    value: Any


def parse_time(raw: Any) -> TimeSelector:
    if isinstance(raw, str):
        if raw in ("first", "last"):
            return TimeSelector("sentinel", raw)
        return TimeSelector("iso", raw)
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(x, str) for x in raw):
        return TimeSelector("range", raw)
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, int):
            return TimeSelector("index", idx)
        if isinstance(idx, list) and all(isinstance(x, int) for x in idx):
            return TimeSelector("index_list", idx)
    raise SelectorError(f"unrecognized time selector: {raw!r}")


def parse_level(raw: Any) -> LevelSelector:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return LevelSelector("numeric", raw)
    if isinstance(raw, list) and all(isinstance(x, (int, float)) for x in raw):
        return LevelSelector("list", list(raw))
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, int):
            return LevelSelector("index", idx)
        if isinstance(idx, list) and all(isinstance(x, int) for x in idx):
            return LevelSelector("index_list", idx)
    if isinstance(raw, str) and raw in ("surface", "top"):
        return LevelSelector("sentinel", raw)
    raise SelectorError(f"unrecognized level selector: {raw!r}")


def parse_latlon(raw: Any) -> LatLonSelector:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return LatLonSelector("point", float(raw))
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(x, (int, float)) for x in raw):
        return LatLonSelector("bbox", [float(raw[0]), float(raw[1])])
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, list) and len(idx) == 2 and all(isinstance(x, int) for x in idx):
            return LatLonSelector("index", idx)
    raise SelectorError(f"unrecognized lat/lon selector: {raw!r}")

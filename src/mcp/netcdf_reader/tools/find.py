# src/mcp/netcdf_reader/tools/find.py
"""⤴ format-agnostic — eligible for _core/ lift.

Hint-based search. Skills layer their own aliases.md on top; standalone
MCP users get usable disambiguation without external alias tables.
"""
from __future__ import annotations

import difflib
from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import classify


def _score(hint: str, candidate: str | None) -> float:
    if not candidate:
        return 0.0
    h = hint.lower()
    c = candidate.lower()
    if h == c:
        return 1.0
    if h in c:
        return 0.85
    return difflib.SequenceMatcher(None, h, c).ratio()


def find_variables(path: str, hint: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        scored: list[tuple[float, dict[str, Any]]] = []
        for name, da in ds.data_vars.items():
            ln = da.attrs.get("long_name")
            sn = da.attrs.get("standard_name")
            desc = da.attrs.get("description")
            best_field = None
            best_value = None
            best_score = 0.0
            for field_name, field_value in (("long_name", ln),
                                            ("standard_name", sn),
                                            ("description", desc),
                                            ("name", str(name))):
                s = _score(hint, field_value)
                if s > best_score:
                    best_score = s
                    best_field = field_name
                    best_value = field_value
            scored.append((best_score, {
                "name": str(name),
                "score": round(best_score, 3),
                "matched_field": best_field,
                "matched_value": best_value,
                "long_name": ln,
                "units": da.attrs.get("units"),
            }))
        scored.sort(key=lambda x: x[0], reverse=True)
        return envelope.success({"matches": [m for _, m in scored[:10]]})
    finally:
        ds.close()


def find_time(path: str, hint: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        tcoord = None
        for n in ("time", "Time", "ocean_time"):
            if n in ds.coords or n in ds.dims:
                tcoord = ds[n].values
                break
        if tcoord is None:
            return envelope.error("internal_error", "no time coord", context={})

        if hint == "first":
            return envelope.success({"matches": [{
                "resolved_time": str(tcoord[0]), "index": 0,
                "match_kind": "exact", "distance": "PT0S",
            }]})
        if hint == "last":
            return envelope.success({"matches": [{
                "resolved_time": str(tcoord[-1]), "index": int(len(tcoord) - 1),
                "match_kind": "exact", "distance": "PT0S",
            }]})

        # Try exact ISO parse + nearest first; an ISO-parseable hint that
        # equals a stored time is "exact" even if its string form is shorter
        # (e.g. "2024-09-01T06:00" vs stored "2024-09-01T06:00:00.000000000").
        try:
            target = np.datetime64(hint)
        except (ValueError, TypeError):
            target = None

        if target is not None:
            diffs = np.abs(tcoord - target)
            sorted_idx = np.argsort(diffs)
            out = []
            for i in sorted_idx[:5]:
                i = int(i)
                d_seconds = int(np.abs(tcoord[i] - target) /
                                np.timedelta64(1, "s"))
                out.append({
                    "resolved_time": str(tcoord[i]),
                    "index": i,
                    "match_kind": "exact" if d_seconds == 0 else "nearest",
                    "distance": f"PT{d_seconds}S",
                })
            return envelope.success({"matches": out})

        # Fallback: partial string match on ISO representations
        iso_strs = [str(t) for t in tcoord]
        partial_matches = [
            (i, s) for i, s in enumerate(iso_strs) if s.startswith(hint)
        ]
        if partial_matches:
            return envelope.success({"matches": [
                {"resolved_time": s, "index": i,
                 "match_kind": "exact" if s == hint else "partial",
                 "distance": "PT0S"}
                for i, s in partial_matches[:10]
            ]})

        return envelope.success({"matches": []})
    finally:
        ds.close()

"""⤴ format-agnostic — eligible for _core/ lift.

Spec-only annotations. The renderer (cycle 2) consumes these
annotations and applies the actual numerical transforms (e.g.,
(da[1:] + da[:-1]) / 2 along a staggered dim).
"""
from __future__ import annotations

import copy
from typing import Any

from src.mcp.netcdf_reader import envelope


def regrid_to_centers(spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    transforms = out.setdefault("applied_transforms", [])
    if not any(t.get("kind") == "regrid_to_centers" for t in transforms):
        transforms.append({"kind": "regrid_to_centers"})
    return envelope.success(out)

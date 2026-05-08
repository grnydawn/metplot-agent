# tests/skills/test_skill_tool_refs.py
"""Verify every <server>.<tool> reference in skill bodies points to a
real MCP tool from cycles 1+2."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill


# Canonical tool lists from cycles 1 and 2 (per their dispatch lists)
_REAL_TOOLS = {
    "netcdf-reader.inspect",
    "netcdf-reader.resolve_spec",
    "netcdf-reader.read_slice",
    "netcdf-reader.compute_stats",
    "netcdf-reader.peek",
    "netcdf-reader.find_variables",
    "netcdf-reader.find_time",
    "netcdf-reader.regrid_to_centers",
    "plot-renderer.render_map",
    "plot-renderer.render_timeseries",
    "plot-renderer.render_profile",
}

# Pattern for `<server>.<tool>` references in skill markdown.
# Matches things like `netcdf-reader.inspect` or `plot-renderer.render_map`
# inside backticks or bare. Excludes things like `netcdf-reader.inspect()` —
# we'll strip the parens.
_TOOL_REF = re.compile(
    r"\b(netcdf-reader|plot-renderer)\.([a-z][a-z0-9_]*)\b"
)

_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _extract_tool_refs(text: str) -> set[str]:
    return {f"{m.group(1)}.{m.group(2)}" for m in _TOOL_REF.finditer(text)}


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_all_tool_refs_real(path: Path) -> None:
    _, body = parse_skill(path)
    refs = _extract_tool_refs(body)
    bad = refs - _REAL_TOOLS
    assert not bad, (
        f"{path.parent.name}: skill body references unknown MCP tools: "
        f"{sorted(bad)}; valid tools: {sorted(_REAL_TOOLS)}")

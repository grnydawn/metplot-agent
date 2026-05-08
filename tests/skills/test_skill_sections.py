# tests/skills/test_skill_sections.py
"""Validate required sections appear in each cycle-3 SKILL.md."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import (
    list_skills, parse_skill, find_sections,
)

# Required L2 sections for every cycle-3 skill, in order.
_REQUIRED_SECTIONS = [
    "When to use",
    "Quick reference",
    # Pitfalls is optional but recommended; we don't require it.
    "Verification",
    "Recording lessons",
    "See also",
]

# netcdf-plot-router is exempt from Verification + Recording lessons since
# it doesn't produce output directly.
_ROUTER_REQUIRED_SECTIONS = [
    "When to use",
    "Quick reference",
    "See also",
]

_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _cycle3_skill_paths() -> list[Path]:
    return [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS]


def _required_for(name: str) -> list[str]:
    if name == "netcdf-plot-router":
        return _ROUTER_REQUIRED_SECTIONS
    return _REQUIRED_SECTIONS


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_required_sections_present(path: Path) -> None:
    _, body = parse_skill(path)
    sections = [t for lvl, t in find_sections(body) if lvl == 2]
    for required in _required_for(path.parent.name):
        assert required in sections, (
            f"{path.parent.name}: missing L2 section {required!r}; "
            f"found {sections}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_sections_in_order(path: Path) -> None:
    _, body = parse_skill(path)
    sections = [t for lvl, t in find_sections(body) if lvl == 2]
    required = _required_for(path.parent.name)
    last_idx = -1
    for r in required:
        idx = sections.index(r)  # raises if missing — caught by previous test
        assert idx > last_idx, (
            f"{path.parent.name}: section {r!r} appears at index {idx} "
            f"but should come after the previous required section "
            f"(last_idx={last_idx})")
        last_idx = idx

# tests/skills/test_skill_frontmatter.py
"""Validate SKILL.md frontmatter shape across all skills."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill


# Skip skill-refiner — that's cycle 6, not in scope for cycle 3
_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _cycle3_skill_paths() -> list[Path]:
    return [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS]


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_frontmatter_required_fields(path: Path) -> None:
    fm, _ = parse_skill(path)
    assert "name" in fm, f"{path.parent.name}: missing 'name' in frontmatter"
    assert "description" in fm, (
        f"{path.parent.name}: missing 'description' in frontmatter")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_name_matches_directory(path: Path) -> None:
    fm, _ = parse_skill(path)
    assert fm["name"] == path.parent.name, (
        f"name {fm['name']!r} != directory {path.parent.name!r}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_description_length(path: Path) -> None:
    fm, _ = parse_skill(path)
    desc = fm["description"]
    assert isinstance(desc, str), f"description must be a string, got {type(desc)}"
    assert 1 <= len(desc) <= 1024, (
        f"description length {len(desc)} out of range [1, 1024] "
        f"for {path.parent.name}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_description_is_single_paragraph(path: Path) -> None:
    """Description should be a single sentence/paragraph (no double newlines)."""
    fm, _ = parse_skill(path)
    assert "\n\n" not in fm["description"], (
        f"{path.parent.name}: description should be a single paragraph")

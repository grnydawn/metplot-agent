# tests/targets/claude_code/test_skills_copied.py
"""Verify skills directory contents."""
from __future__ import annotations

from pathlib import Path

import pytest


_EXPECTED_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def test_all_expected_skills_present(built_plugin: Path) -> None:
    skills_dir = built_plugin / "skills"
    actual = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    assert actual == _EXPECTED_SKILLS, (
        f"unexpected skill set: missing {_EXPECTED_SKILLS - actual}, "
        f"extra {actual - _EXPECTED_SKILLS}")


def test_skill_refiner_excluded(built_plugin: Path) -> None:
    """skill-refiner is cycle 6; must not be in the build."""
    assert not (built_plugin / "skills" / "skill-refiner").exists()


@pytest.mark.parametrize("skill", sorted(_EXPECTED_SKILLS))
def test_skill_md_present(built_plugin: Path, skill: str) -> None:
    md = built_plugin / "skills" / skill / "SKILL.md"
    assert md.is_file()
    text = md.read_text()
    assert text.startswith("---\n"), f"{skill} SKILL.md missing frontmatter"


def test_references_subdirs_preserved(built_plugin: Path) -> None:
    """Skills with references/ subdirs must still have them after copy."""
    inspect_refs = built_plugin / "skills" / "netcdf-inspect" / "references"
    assert inspect_refs.is_dir()
    assert (inspect_refs / "aliases.md").is_file()
    assert (inspect_refs / "conventions.md").is_file()

    map_refs = built_plugin / "skills" / "netcdf-plot-map" / "references"
    assert map_refs.is_dir()
    assert (map_refs / "regions.md").is_file()
    assert (map_refs / "regions.json").is_file()
    assert (map_refs / "colormaps.json").is_file()

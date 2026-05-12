# tests/targets/cursor/test_skills_copied.py
from pathlib import Path

import pytest


_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    "skill-refiner",
}


def test_all_expected_skills_present(built_plugin: Path):
    actual = {p.name for p in (built_plugin / "skills").iterdir() if p.is_dir()}
    assert actual == _EXPECTED


def test_skill_refiner_included(built_plugin: Path):
    assert (built_plugin / "skills" / "skill-refiner" / "SKILL.md").is_file()


@pytest.mark.parametrize("skill", sorted(_EXPECTED))
def test_skill_md_present(built_plugin: Path, skill: str):
    assert (built_plugin / "skills" / skill / "SKILL.md").is_file()

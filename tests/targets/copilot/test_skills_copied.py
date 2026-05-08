# tests/targets/copilot/test_skills_copied.py
from pathlib import Path

import pytest


_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def test_all_expected_skills_present(built_plugin: Path):
    actual = {p.name for p in (built_plugin / "skills").iterdir() if p.is_dir()}
    assert actual == _EXPECTED


def test_skill_refiner_excluded(built_plugin: Path):
    assert not (built_plugin / "skills" / "skill-refiner").exists()


@pytest.mark.parametrize("skill", sorted(_EXPECTED))
def test_skill_md_present(built_plugin: Path, skill: str):
    assert (built_plugin / "skills" / skill / "SKILL.md").is_file()

# tests/targets/antigravity/test_skills_copied.py
from pathlib import Path
import pytest

_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    "skill-refiner",
}

def test_skills_under_agent_dir(built_plugin: Path):
    skills = built_plugin / ".agent" / "skills"
    assert skills.is_dir()

def test_all_expected_skills(built_plugin: Path):
    actual = {p.name for p in (built_plugin / ".agent" / "skills").iterdir() if p.is_dir()}
    assert actual == _EXPECTED

def test_skill_refiner_included(built_plugin: Path):
    assert (built_plugin / ".agent" / "skills" / "skill-refiner" / "SKILL.md").is_file()

@pytest.mark.parametrize("skill", sorted(_EXPECTED))
def test_skill_md_present(built_plugin: Path, skill: str):
    assert (built_plugin / ".agent" / "skills" / skill / "SKILL.md").is_file()

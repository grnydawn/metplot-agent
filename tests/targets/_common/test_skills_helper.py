# tests/targets/_common/test_skills_helper.py
from pathlib import Path

import pytest

from targets._common.skills import INCLUDED_SKILLS, copy_skills


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def test_included_skills_set():
    assert INCLUDED_SKILLS == frozenset({
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    })


def test_skill_refiner_not_included():
    assert "skill-refiner" not in INCLUDED_SKILLS


def test_copy_skills_creates_dir_and_returns_names(tmp_path):
    out = tmp_path / "skills"
    names = copy_skills(SRC_ROOT, out)
    assert sorted(names) == sorted(INCLUDED_SKILLS)
    for name in names:
        assert (out / name / "SKILL.md").is_file()
    # Refiner explicitly absent
    assert not (out / "skill-refiner").exists()


def test_copy_skills_raises_on_missing_source(tmp_path):
    bad_src = tmp_path / "nope"
    bad_src.mkdir()
    with pytest.raises(RuntimeError):
        copy_skills(bad_src, tmp_path / "out")

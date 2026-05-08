# targets/_common/skills.py
"""Shared cycle-3 skills allowlist + copy helper used by every build target."""
from __future__ import annotations

import shutil
from pathlib import Path


INCLUDED_SKILLS = frozenset({
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
})


def copy_skills(src_root: Path, dst_skills_dir: Path) -> list[str]:
    """Copy each cycle-3 skill from `src_root/skills/<name>/` into
    `dst_skills_dir/<name>/`. Excludes `skill-refiner` (cycle 6).

    Creates `dst_skills_dir` if missing.

    Returns the list of skill names copied.
    Raises RuntimeError if any allowlisted skill is missing from the source.
    """
    skills_src = src_root / "skills"
    if not skills_src.is_dir():
        raise RuntimeError(f"skills source missing: {skills_src}")
    dst_skills_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in sorted(INCLUDED_SKILLS):
        src = skills_src / name
        if not src.is_dir():
            raise RuntimeError(f"missing skill source: {src}")
        shutil.copytree(src, dst_skills_dir / name)
        copied.append(name)
    return copied

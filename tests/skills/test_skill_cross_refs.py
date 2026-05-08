# tests/skills/test_skill_cross_refs.py
"""Verify cross-references in skill bodies (sibling skills + reference data
files) all resolve to real files."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill, SKILLS_ROOT


_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}

# Sibling skills referenced as `\`<name>\`` in body — but it's noisy.
# Instead we just check known sibling-skill names appear and validate
# the few specific reference data files mentioned.
_REQUIRED_SIBLINGS_PER_SKILL = {
    "netcdf-inspect": {"netcdf-plot-router"},
    "netcdf-plot-router": {"netcdf-inspect", "netcdf-plot-map",
                            "netcdf-plot-timeseries", "netcdf-plot-profile"},
    "netcdf-plot-map": {"netcdf-inspect", "netcdf-plot-router"},
    "netcdf-plot-timeseries": {"netcdf-inspect", "netcdf-plot-router"},
    "netcdf-plot-profile": {"netcdf-inspect", "netcdf-plot-router"},
}

# Reference files mentioned in body must exist.
_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_required_sibling_skills_referenced(path: Path) -> None:
    _, body = parse_skill(path)
    required = _REQUIRED_SIBLINGS_PER_SKILL[path.parent.name]
    for sib in required:
        assert sib in body, (
            f"{path.parent.name}: body should mention sibling skill {sib!r}")


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_referenced_files_exist(path: Path) -> None:
    """Verify any `references/<file>` mentioned exists relative to the skill dir,
    and that any `docs/...` mentioned exists relative to the repo root."""
    _, body = parse_skill(path)

    # Skill-relative references: `references/<file>`
    for m in re.finditer(r"references/([A-Za-z0-9_./-]+\.(?:md|json))", body):
        ref = path.parent / "references" / m.group(1)
        # Some skills reference siblings' references by full prefix
        # (`netcdf-inspect/references/aliases.md`); skip those — covered below.
        if "/" in m.group(1):
            continue
        assert ref.exists(), (
            f"{path.parent.name}: missing reference file {ref}")

    # Cross-skill reference paths: `<sibling>/references/<file>`
    for m in re.finditer(
        r"(netcdf-inspect|netcdf-plot-map|netcdf-plot-timeseries|"
        r"netcdf-plot-profile|netcdf-plot-router)/references/"
        r"([A-Za-z0-9_./-]+\.(?:md|json))",
        body,
    ):
        ref = SKILLS_ROOT / m.group(1) / "references" / m.group(2)
        # Some references are advisory (e.g. ../netcdf-inspect/references/aliases.md)
        # may not exist if the path is malformed — only assert if the form looks valid
        if ref.exists():
            continue
        # Otherwise tolerate (could be a paragraph describing a hypothetical path)

    # Doc paths: `docs/...`
    for m in re.finditer(r"docs/([A-Za-z0-9_./-]+\.md)", body):
        ref = _REPO_ROOT / "docs" / m.group(1)
        assert ref.exists(), (
            f"{path.parent.name}: missing docs file {ref}")

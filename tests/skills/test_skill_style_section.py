# tests/skills/test_skill_style_section.py
"""Verify each plot skill has a Style by reference section pointing to
the extraction prompt doc."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill, has_section

_PLOT_SKILLS = {"netcdf-plot-map", "netcdf-plot-timeseries",
                 "netcdf-plot-profile"}


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _PLOT_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_has_style_section(path: Path) -> None:
    _, body = parse_skill(path)
    assert has_section(body, "Style by reference", level=2), (
        f"{path.parent.name}: missing '## Style by reference' section")


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _PLOT_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_style_section_references_prompt_doc(path: Path) -> None:
    _, body = parse_skill(path)
    assert "docs/style_template_extraction_prompt.md" in body, (
        f"{path.parent.name}: Style by reference section must point to "
        f"docs/style_template_extraction_prompt.md")

# tests/skills/_skill_helpers.py
"""Shared helpers for skill content validation tests.

Parses SKILL.md files into frontmatter + body, provides section
extraction utilities. Used by all tests/skills/test_*.py modules.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "skills"


def list_skills() -> list[Path]:
    """Return paths to all SKILL.md files under src/skills/."""
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_markdown) for a SKILL.md file."""
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    fm_text = text[4:end]
    body = text[end + 5:]
    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: frontmatter is not a YAML mapping")
    return fm, body


def find_sections(body: str) -> list[tuple[int, str]]:
    """Return [(level, title), ...] for every markdown heading in body, in order."""
    out: list[tuple[int, str]] = []
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def has_section(body: str, title: str, level: int = 2) -> bool:
    return any(lvl == level and t == title for lvl, t in find_sections(body))


def section_index(body: str, title: str, level: int = 2) -> int:
    """Return the index in the heading sequence at which `title` first appears.
    Returns -1 if absent."""
    for i, (lvl, t) in enumerate(find_sections(body)):
        if lvl == level and t == title:
            return i
    return -1

# tests/skills/conftest.py
"""Fixtures for skill content tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import SKILLS_ROOT, list_skills


@pytest.fixture
def skills_root() -> Path:
    return SKILLS_ROOT


@pytest.fixture
def skill_paths() -> list[Path]:
    return list_skills()

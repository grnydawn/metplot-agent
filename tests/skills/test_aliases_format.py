# tests/skills/test_aliases_format.py
"""Validate aliases.md has the refiner-insert markers in correct positions."""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALIASES = (_REPO_ROOT / "src" / "skills" / "netcdf-inspect"
             / "references" / "aliases.md")


def test_refiner_markers_present():
    text = _ALIASES.read_text()
    assert "<!-- REFINER_INSERT_BELOW -->" in text
    assert "<!-- REFINER_INSERT_ABOVE -->" in text


def test_refiner_markers_in_order():
    text = _ALIASES.read_text()
    below_idx = text.index("<!-- REFINER_INSERT_BELOW -->")
    above_idx = text.index("<!-- REFINER_INSERT_ABOVE -->")
    assert below_idx < above_idx, (
        "REFINER_INSERT_BELOW must appear before REFINER_INSERT_ABOVE")


def test_aliases_has_required_sections():
    text = _ALIASES.read_text()
    required = [
        "## Sea surface temperature",
        "## 2-meter air temperature",
        "## Precipitation",
        "## Wind components",
    ]
    for sec in required:
        assert sec in text, f"aliases.md: missing section {sec!r}"

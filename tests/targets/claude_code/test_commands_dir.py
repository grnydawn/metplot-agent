# tests/targets/claude_code/test_commands_dir.py
"""Verify commands/ has the shipped /refine command (no longer a placeholder).

Detailed body assertions live in test_refine_real.py; this file holds
the structural shape checks (file present, frontmatter parses)."""
from __future__ import annotations

from pathlib import Path


def test_commands_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / "commands").is_dir()


def test_refine_command_present(built_plugin: Path) -> None:
    assert (built_plugin / "commands" / "refine.md").is_file()


def test_refine_has_frontmatter(built_plugin: Path) -> None:
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end > 0, "refine.md frontmatter unterminated"

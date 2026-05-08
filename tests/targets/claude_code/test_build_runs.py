# tests/targets/claude_code/test_build_runs.py
"""Verify the cycle-4 Claude Code build produces all expected top-level
files and directories."""
from __future__ import annotations

from pathlib import Path


def test_plugin_root_exists(built_plugin: Path) -> None:
    assert built_plugin.is_dir()
    assert built_plugin.name == "ncplot"


def test_manifest_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / ".claude-plugin").is_dir()
    assert (built_plugin / ".claude-plugin" / "plugin.json").is_file()


def test_top_level_dirs_present(built_plugin: Path) -> None:
    for d in ("skills", "mcp-servers", "commands"):
        assert (built_plugin / d).is_dir(), f"missing top-level dir: {d}"


def test_top_level_files_present(built_plugin: Path) -> None:
    assert (built_plugin / ".mcp.json").is_file()
    assert (built_plugin / "README.md").is_file()


def test_hooks_dir_present(built_plugin: Path) -> None:
    """Cycle-5 adds hooks/ with the SessionStart setup hook."""
    assert (built_plugin / "hooks").is_dir()


def test_build_is_idempotent(tmp_path_factory, build_module) -> None:
    """Running build twice produces the same shape (clean overwrite)."""
    out = tmp_path_factory.mktemp("idem")
    src = Path(__file__).resolve().parents[3] / "src"
    build_module.build(src, out)
    first_files = sorted((p.relative_to(out) for p in out.rglob("*")
                           if p.is_file()))
    build_module.build(src, out)
    second_files = sorted((p.relative_to(out) for p in out.rglob("*")
                            if p.is_file()))
    assert first_files == second_files

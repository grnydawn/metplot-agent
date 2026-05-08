"""Smoke tests for skill format and build pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"
SKILLS = SRC / "skills"


def test_skills_directory_exists():
    assert SKILLS.exists(), f"missing skills directory at {SKILLS}"


def test_every_skill_has_skill_md():
    for d in SKILLS.iterdir():
        if d.is_dir():
            assert (d / "SKILL.md").exists(), f"{d.name} has no SKILL.md"


def test_skills_lint_clean():
    """All canonical skills pass the linter."""
    from tools.lint_skills import lint_skill

    for d in sorted(SKILLS.iterdir()):
        if not d.is_dir():
            continue
        issues = lint_skill(d)
        assert not issues, f"{d.name}: {issues}"


def test_targets_have_build_module():
    targets_root = REPO_ROOT / "targets"
    assert targets_root.exists()
    targets = [p for p in targets_root.iterdir()
               if p.is_dir() and not p.name.startswith("_")]
    assert targets, "no targets registered"
    for t in targets:
        assert (t / "build.py").exists(), f"{t.name} missing build.py"


def test_build_dispatcher_imports():
    """The dispatcher should import without errors."""
    from tools import build  # noqa: F401


@pytest.mark.parametrize("target", ["claude-code", "claude-desktop", "codex", "hermes"])
def test_target_build_runs(tmp_path, target):
    """Each target builder should run and produce something."""
    from tools.build import discover_targets, load_target_module

    targets = discover_targets()
    assert target in targets, f"target {target} not registered"
    module = load_target_module(target, targets[target])
    module.build(SRC, tmp_path)
    # at least one file should have landed
    assert any(tmp_path.rglob("*")), f"build({target}) produced nothing"

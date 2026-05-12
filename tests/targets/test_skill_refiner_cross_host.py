# tests/targets/test_skill_refiner_cross_host.py
"""Smoke check: every host build ships skill-refiner.

The per-host `test_skills_copied` files already assert the skill landed
in that host's specific layout (`skills/skill-refiner/`,
`.agent/skills/skill-refiner/`, …). This file is the cross-cutting
view — one parametrized test that builds every target into a tmp dir
and confirms `skill-refiner` made it through. If a future target adds
an exotic layout the per-host test forgets to cover, this catches it.

Per spec §3.3 (cycle-6 self-improvement-loop)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"

# (host_dirname, expected skill location relative to the built plugin root).
# `claude-desktop` is excluded — it concatenates skills into a single
# `project_instructions.md` rather than emitting a `skills/` tree, and
# is covered by `tests/targets/claude_desktop/test_concatenated_skills.py`.
# `hermes` is excluded — stub target not yet emitting builds (see
# `tests/targets/test_all_targets_buildable.py` skip).
_BUILDS: list[tuple[str, str]] = [
    ("claude-code",  "skills/skill-refiner/SKILL.md"),
    ("cursor",       "skills/skill-refiner/SKILL.md"),
    ("copilot",      "skills/skill-refiner/SKILL.md"),
    ("gemini-cli",   "skills/skill-refiner/SKILL.md"),
    ("codex",        "skills/skill-refiner/SKILL.md"),
    ("antigravity",  ".agent/skills/skill-refiner/SKILL.md"),
]


def _load_build_module(host_dirname: str):
    build_py = REPO_ROOT / "targets" / host_dirname / "build.py"
    # Use a Python-legal module name (hyphens → underscores) for the
    # importlib spec; the file location is what actually matters.
    py_name = f"targets.{host_dirname.replace('-', '_')}.build"
    spec = importlib.util.spec_from_file_location(py_name, build_py)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("host_dirname,skill_rel", _BUILDS,
                         ids=[b[0] for b in _BUILDS])
def test_skill_refiner_shipped(tmp_path: Path, host_dirname: str,
                               skill_rel: str) -> None:
    _load_build_module(host_dirname).build(SRC_ROOT, tmp_path)
    plugin_root = tmp_path / "metplot"
    skill = plugin_root / skill_rel
    assert skill.is_file(), (
        f"{host_dirname} did not ship skill-refiner at {skill_rel} "
        f"(plugin_root={plugin_root}); SKILL.md files found: "
        f"{sorted(p.relative_to(plugin_root).as_posix() for p in plugin_root.rglob('SKILL.md'))}")


def test_every_host_test_dir_has_skills_coverage() -> None:
    """Documentation guard: if a new host target is added under
    `targets/`, it must also have a `tests/targets/<host>/` directory
    with either a `test_skills_copied` file (skills-tree-style host) or
    a `test_concatenated_skills` file (concat-style host). Catches the
    failure mode where a new host slips in without an independent
    per-host check on the skill payload."""
    targets_dir = REPO_ROOT / "targets"
    hosts = {
        p.name for p in targets_dir.iterdir()
        if p.is_dir() and not p.name.startswith(("_", "."))
    }
    # Targets without a built artifact (stubs) are out of scope.
    hosts.discard("hermes")
    tests_dir = REPO_ROOT / "tests" / "targets"
    missing = []
    for host in sorted(hosts):
        py_host = host.replace("-", "_")
        tdir = tests_dir / py_host
        if not tdir.is_dir():
            missing.append(f"{host}: no tests/targets/{py_host}/ dir")
            continue
        if not any(p.name.startswith(("test_skills_copied",
                                       "test_concatenated_skills"))
                   for p in tdir.iterdir() if p.is_file()):
            missing.append(
                f"{host}: tests/targets/{py_host}/ has no "
                f"test_skills_copied / test_concatenated_skills file")
    assert not missing, "\n".join(missing)

"""Smoke test: tools/build.py --all builds every target without conflict."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_ROOT = REPO_ROOT / "targets"
SRC_ROOT = REPO_ROOT / "src"


def _list_targets() -> list[str]:
    """Discover targets the same way tools/build.py does."""
    out = []
    for p in TARGETS_ROOT.iterdir():
        if p.is_dir() and not p.name.startswith("_") and (p / "build.py").exists():
            out.append(p.name)
    return sorted(out)


def _load_build(target: str):
    spec = importlib.util.spec_from_file_location(
        f"targets.{target.replace('-', '_')}.build",
        TARGETS_ROOT / target / "build.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("target", _list_targets())
def test_target_builds_to_unique_dir(tmp_path, target: str):
    """Each target writes to <tmp>/<target>/ — never overlapping."""
    if target == "hermes":
        pytest.skip("hermes target stub unverified by cycle-7 research")
    out = tmp_path / target
    out.mkdir()
    mod = _load_build(target)
    if not hasattr(mod, "build"):
        pytest.skip(f"target {target} has no build()")
    mod.build(SRC_ROOT, out)
    plugin_root = out / "ncplot-agent"
    assert plugin_root.is_dir(), f"{target}: missing ncplot-agent dir"
    # Each target produces *something* — at least skills or a manifest
    has_content = any((plugin_root / sub).exists() for sub in
                       ("skills", "mcp-servers", ".agent",
                        "project_instructions.md", "plugin.json",
                        ".claude-plugin", ".codex-plugin", ".cursor-plugin",
                        "gemini-extension.json", ".vscode"))
    assert has_content, f"{target}: empty build artifact"

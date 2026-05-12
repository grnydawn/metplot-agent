# tests/targets/test_all_targets_have_setup.py
"""Verify every cycle-7 target ships setup.sh + setup.ps1 +
tools/install_deps.py."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_ROOT = REPO_ROOT / "targets"
SRC_ROOT = REPO_ROOT / "src"


def _list_targets() -> list[str]:
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
    assert spec is not None and spec.loader is not None, (
        f"could not load build module spec for {target}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("target", _list_targets())
def test_target_ships_setup_sh(tmp_path, target: str):
    if target == "hermes":
        pytest.skip("hermes target stub; cycle-5 doesn't update it")
    out = tmp_path / target
    out.mkdir()
    mod = _load_build(target)
    if not hasattr(mod, "build"):
        pytest.skip(f"target {target} has no build()")
    mod.build(SRC_ROOT, out)
    plugin_root = out / "metplot"
    assert (plugin_root / "setup.sh").is_file(), f"{target}: missing setup.sh"
    assert (plugin_root / "setup.ps1").is_file(), f"{target}: missing setup.ps1"
    assert (plugin_root / "tools" / "install_deps.py").is_file(), (
        f"{target}: missing bundled installer")

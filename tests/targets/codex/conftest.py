"""Build the Codex plugin into a tmp dir; module-scoped fixture."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "codex" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "targets.codex.build", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("build-codex")
    mod = _load_build_module()
    mod.build(SRC_ROOT, out)
    plugin_root = out / "metplot"
    assert plugin_root.is_dir()
    return plugin_root


@pytest.fixture(scope="module")
def build_module():
    return _load_build_module()

# tests/targets/claude_code/conftest.py
"""Fixtures for Claude Code build-output tests.

Builds the plugin into tmp_path once per test module; tests reuse
the produced artifact.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "claude-code" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "targets.claude_code.build", BUILD_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {BUILD_PY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory) -> Path:
    """Build the plugin into a tmp dir; return the plugin root path."""
    out_dir = tmp_path_factory.mktemp("build")
    mod = _load_build_module()
    mod.build(SRC_ROOT, out_dir)
    plugin_root = out_dir / mod.PLUGIN_NAME
    assert plugin_root.is_dir(), f"build did not produce {plugin_root}"
    return plugin_root


@pytest.fixture(scope="module")
def build_module():
    return _load_build_module()

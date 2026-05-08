# tests/tools/test_build_dispatcher.py
"""Verify tools/build.py discovers + builds the claude-code target."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dispatcher():
    spec = importlib.util.spec_from_file_location(
        "tools.build", REPO_ROOT / "tools" / "build.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_discover_targets_finds_claude_code():
    mod = _load_dispatcher()
    targets = mod.discover_targets()
    assert "claude-code" in targets


def test_validation_dir_mapping():
    mod = _load_dispatcher()
    p = mod._validation_dir_for("claude-code")
    assert p.name == "claude_code"


def test_build_via_dispatcher(tmp_path, monkeypatch):
    """Running the dispatcher's build_target programmatically produces output."""
    mod = _load_dispatcher()
    monkeypatch.setattr(mod, "BUILD_ROOT", tmp_path)
    mod.build_target("claude-code", validate=False)
    plugin_root = tmp_path / "claude-code" / "ncplot-agent"
    assert plugin_root.is_dir()
    assert (plugin_root / ".claude-plugin" / "plugin.json").is_file()


def test_build_unknown_target_raises():
    import click
    mod = _load_dispatcher()
    with pytest.raises(click.ClickException):
        mod.build_target("not-a-real-target")

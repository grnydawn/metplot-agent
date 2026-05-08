# tests/targets/codex/test_no_hooks.py
from pathlib import Path
import json


def test_no_hooks_dir(built_plugin: Path):
    """Codex hooks land with skill-refiner in cycle 6."""
    assert not (built_plugin / "hooks").exists()


def test_manifest_has_no_hooks(built_plugin: Path):
    m = json.loads((built_plugin / ".codex-plugin" / "plugin.json").read_text())
    assert "hooks" not in m or not m["hooks"]

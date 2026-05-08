# tests/targets/antigravity/test_no_hooks.py
from pathlib import Path


def test_no_hooks_dir(built_plugin: Path):
    """Antigravity has no hook system as of cycle 7."""
    assert not (built_plugin / "hooks").exists()

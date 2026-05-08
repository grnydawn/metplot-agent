# tests/targets/claude_code/test_no_hooks.py
"""Verify hooks/ is deferred to cycle 6 and not present in cycle 4."""
from __future__ import annotations

from pathlib import Path


def test_no_hooks_dir(built_plugin: Path) -> None:
    """Stop hook for skill-refiner ships in cycle 6, not cycle 4."""
    assert not (built_plugin / "hooks").exists()


def test_manifest_has_no_hook_config(built_plugin: Path) -> None:
    """plugin.json should not declare any hooks in cycle 4."""
    import json
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    # The manifest may not have a 'hooks' key at all (preferred), OR if it
    # does, it should be an empty list/dict.
    if "hooks" in m:
        assert not m["hooks"], (
            f"manifest declares hooks in cycle 4: {m['hooks']!r}")

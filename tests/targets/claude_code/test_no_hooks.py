# tests/targets/claude_code/test_no_hooks.py
"""Cycle-5: hooks/ now exists (SessionStart setup hook). Verify only the
manifest has no 'hooks' key — that's a plugin.json concern, not the dir."""
from __future__ import annotations

import json
from pathlib import Path


def test_manifest_has_no_hook_config(built_plugin: Path) -> None:
    """plugin.json should not declare any hooks (hooks are in hooks/ dir)."""
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    if "hooks" in m:
        assert not m["hooks"], (
            f"manifest declares hooks unexpectedly: {m['hooks']!r}")

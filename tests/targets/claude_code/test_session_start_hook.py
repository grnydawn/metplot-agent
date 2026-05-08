import json
from pathlib import Path


def test_hook_present(built_plugin: Path):
    assert (built_plugin / "hooks" / "setup.json").is_file()


def test_hook_session_start_event(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    assert "SessionStart" in h
    cmds = h["SessionStart"][0]["hooks"]
    assert any("setup.sh" in c["command"] for c in cmds)


def test_hook_uses_quiet_flag(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    cmd = h["SessionStart"][0]["hooks"][0]["command"]
    assert "--quiet" in cmd


def test_hook_uses_plugin_root_var(built_plugin: Path):
    h = json.loads((built_plugin / "hooks" / "setup.json").read_text())
    cmd = h["SessionStart"][0]["hooks"][0]["command"]
    assert "${CLAUDE_PLUGIN_ROOT}" in cmd

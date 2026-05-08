from pathlib import Path


def test_plugin_root(built_plugin: Path):
    assert built_plugin.is_dir()


def test_manifest_at_root(built_plugin: Path):
    """Copilot manifest is at the root, NOT in a subdirectory."""
    assert (built_plugin / "plugin.json").is_file()
    assert not (built_plugin / ".copilot-plugin").exists()
    assert not (built_plugin / ".claude-plugin").exists()


def test_vscode_dir_present(built_plugin: Path):
    assert (built_plugin / ".vscode" / "mcp.json").is_file()


def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()

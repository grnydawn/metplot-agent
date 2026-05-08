from pathlib import Path


def test_root_present(built_plugin: Path):
    assert built_plugin.is_dir()


def test_no_top_level_manifest(built_plugin: Path):
    """Claude Desktop bundle has no plugin manifest."""
    for f in ("plugin.json", ".claude-plugin", ".cursor-plugin",
               "gemini-extension.json"):
        assert not (built_plugin / f).exists()


def test_required_files(built_plugin: Path):
    for f in ("project_instructions.md",
               "claude_desktop_config_snippet.json", "README.md",
               ".metplot.json"):
        assert (built_plugin / f).is_file()

from pathlib import Path

def test_no_top_level_manifest(built_plugin: Path):
    """Antigravity has no top-level plugin manifest."""
    for f in ("plugin.json", ".claude-plugin", ".codex-plugin",
               ".cursor-plugin", "gemini-extension.json"):
        assert not (built_plugin / f).exists(), (
            f"unexpected manifest: {f}")

def test_ncplot_metadata_file_present(built_plugin: Path):
    """Build still writes a hidden cross-target audit file."""
    assert (built_plugin / ".ncplot.json").is_file()

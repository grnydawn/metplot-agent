# tests/targets/gemini_cli/test_build_runs.py
from pathlib import Path


def test_plugin_root_exists(built_plugin: Path):
    assert built_plugin.is_dir()
    assert built_plugin.name == "metplot"


def test_extension_json_present(built_plugin: Path):
    assert (built_plugin / "gemini-extension.json").is_file()


def test_top_level_present(built_plugin: Path):
    for f in ("settings.json", "README.md"):
        assert (built_plugin / f).is_file(), f"missing {f}"
    for d in ("skills", "mcp-servers", "commands"):
        assert (built_plugin / d).is_dir(), f"missing dir {d}"


def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()

# tests/targets/cursor/test_build_runs.py
from pathlib import Path


def test_plugin_root_exists(built_plugin: Path):
    assert built_plugin.is_dir()
    assert built_plugin.name == "ncplot-agent"


def test_cursor_plugin_manifest(built_plugin: Path):
    assert (built_plugin / ".cursor-plugin" / "plugin.json").is_file()


def test_cursor_mcp_json(built_plugin: Path):
    assert (built_plugin / ".cursor" / "mcp.json").is_file()


def test_commands_refine(built_plugin: Path):
    assert (built_plugin / "commands" / "refine.md").is_file()


def test_readme_present(built_plugin: Path):
    assert (built_plugin / "README.md").is_file()


def test_skills_dir_present(built_plugin: Path):
    assert (built_plugin / "skills").is_dir()


def test_mcp_servers_dir_present(built_plugin: Path):
    assert (built_plugin / "mcp-servers").is_dir()


def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()

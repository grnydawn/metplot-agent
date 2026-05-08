# tests/targets/antigravity/test_build_runs.py
from pathlib import Path


def test_plugin_root_exists(built_plugin: Path):
    assert built_plugin.is_dir()
    assert built_plugin.name == "ncplot-agent"


def test_agent_dir_present(built_plugin: Path):
    assert (built_plugin / ".agent").is_dir()


def test_skills_under_agent(built_plugin: Path):
    assert (built_plugin / ".agent" / "skills").is_dir()


def test_workflows_under_agent(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows").is_dir()


def test_mcp_config_snippet_present(built_plugin: Path):
    assert (built_plugin / "mcp_config.json").is_file()


def test_mcp_servers_bundled(built_plugin: Path):
    assert (built_plugin / "mcp-servers").is_dir()


def test_readme_present(built_plugin: Path):
    assert (built_plugin / "README.md").is_file()


def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()

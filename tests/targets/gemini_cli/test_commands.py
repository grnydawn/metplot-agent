# tests/targets/gemini_cli/test_commands.py
# Cycle-5: refine.toml moved into commands/ncplot/ subdir (namespace pattern).
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_refine_toml_present(built_plugin: Path):
    assert (built_plugin / "commands" / "ncplot" / "refine.toml").is_file()


def test_refine_toml_not_at_top_level(built_plugin: Path):
    assert not (built_plugin / "commands" / "refine.toml").exists()


def test_refine_toml_parses(built_plugin: Path):
    d = tomllib.loads((built_plugin / "commands" / "ncplot" / "refine.toml").read_text())
    assert "description" in d
    assert "prompt" in d


def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / "commands" / "ncplot" / "refine.toml").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()


def test_setup_toml_in_ncplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "ncplot" / "setup.toml").is_file()


def test_refine_moved_to_ncplot_subdir(built_plugin: Path):
    assert (built_plugin / "commands" / "ncplot" / "refine.toml").is_file()
    assert not (built_plugin / "commands" / "refine.toml").exists()

# tests/targets/gemini_cli/test_commands.py
from pathlib import Path
import sys

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def test_refine_toml_present(built_plugin: Path):
    assert (built_plugin / "commands" / "refine.toml").is_file()


def test_refine_toml_parses(built_plugin: Path):
    d = tomllib.loads((built_plugin / "commands" / "refine.toml").read_text())
    assert "description" in d
    assert "prompt" in d


def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.toml").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()

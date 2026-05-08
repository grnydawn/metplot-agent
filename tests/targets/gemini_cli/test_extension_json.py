# tests/targets/gemini_cli/test_extension_json.py
import json
from pathlib import Path


def test_extension_json_parses(built_plugin: Path):
    json.loads((built_plugin / "gemini-extension.json").read_text())


def test_required_fields(built_plugin: Path):
    m = json.loads((built_plugin / "gemini-extension.json").read_text())
    for f in ("name", "version", "description"):
        assert f in m
    assert m["skills"] == "skills"
    assert m["commands"] == "commands"


def test_ncplot_block(built_plugin: Path):
    m = json.loads((built_plugin / "gemini-extension.json").read_text())
    assert m["ncplot"]["build_cycle"] == 7

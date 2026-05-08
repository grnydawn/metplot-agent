# tests/targets/codex/test_manifest.py
import json
from pathlib import Path


def test_manifest_parses(built_plugin: Path):
    json.loads((built_plugin / ".codex-plugin" / "plugin.json").read_text())


def test_required_fields(built_plugin: Path):
    m = json.loads((built_plugin / ".codex-plugin" / "plugin.json").read_text())
    for f in ("name", "version", "description"):
        assert f in m


def test_ncplot_block_cycle_7(built_plugin: Path):
    m = json.loads((built_plugin / ".codex-plugin" / "plugin.json").read_text())
    assert m["ncplot"]["build_cycle"] == 7

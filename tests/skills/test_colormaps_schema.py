# tests/skills/test_colormaps_schema.py
import json
from pathlib import Path

import pytest


_PATH = (Path(__file__).resolve().parents[2]
         / "src" / "skills" / "netcdf-plot-map"
         / "references" / "colormaps.json")


def _load() -> dict:
    return json.loads(_PATH.read_text())


def test_file_parses():
    assert isinstance(_load(), dict)


def test_schema_version_pinned():
    assert _load()["schema_version"] == 1


def test_default_present():
    d = _load()
    assert "default" in d
    assert d["default"]["cmap"] == "viridis"
    assert d["default"]["kind"] == "sequential"


def _all_entries() -> list[tuple[str, dict]]:
    d = _load()
    out = list(d["by_field_character"].items())
    out.append(("default", d["default"]))
    out.append(("diverging_default", d["diverging_default"]))
    return out


@pytest.mark.parametrize("name,entry", _all_entries())
def test_entry_has_cmap_and_kind(name: str, entry: dict):
    assert "cmap" in entry, f"entry {name!r} missing cmap"
    assert "kind" in entry, f"entry {name!r} missing kind"
    assert entry["kind"] in {"sequential", "diverging", "categorical"}, (
        f"entry {name!r} has invalid kind {entry['kind']!r}")


@pytest.mark.parametrize("name,entry", _all_entries())
def test_cmap_in_matplotlib_registry(name: str, entry: dict):
    import matplotlib as mpl
    assert entry["cmap"] in mpl.colormaps, (
        f"entry {name!r}: cmap {entry['cmap']!r} not in matplotlib registry")

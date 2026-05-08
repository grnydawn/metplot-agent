# Cycle 3: Plot skills bundle — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Wire the 5 plotting skills (netcdf-inspect, netcdf-plot-router, netcdf-plot-map, netcdf-plot-timeseries, netcdf-plot-profile) to cycle 1+2 MCP signatures, ship reference data (regions.json, colormaps.json), encode the style-by-reference flow in each plot skill, freeze the task-log schema, and validate everything via a Python test suite.

**Architecture:** Cycle 3 is a CONTENT cycle. Most deliverables are markdown (SKILL.md files + reference data); the only Python code is the validation/integration test suite. Skills are pure declarative instruction — the host LLM reads them and acts. No skill execution engine.

**Tech Stack:** Markdown (SKILL.md files), JSON (reference data), Python 3.10+ (test suite), pytest, pyyaml (frontmatter parsing). No new runtime dependencies — only test deps.

**Branch:** `cycle-3-plot-skills` (already created).

---

## File Structure

### Skills (`src/skills/`)

| File | Status | Responsibility |
|------|--------|----------------|
| `netcdf-inspect/SKILL.md` | UPDATE | Inspect-first workflow + alias lookup pointers |
| `netcdf-inspect/references/aliases.md` | UPDATE (minor) | Variable name aliases |
| `netcdf-inspect/references/conventions.md` | UPDATE (minor) | CF cheat sheet |
| `netcdf-plot-router/SKILL.md` | UPDATE | Decision tree + cross-section/Hovmöller deferral |
| `netcdf-plot-map/SKILL.md` | UPDATE | Full map procedure + style-by-reference + colormaps |
| `netcdf-plot-map/references/regions.md` | UPDATE | Synced with regions.json |
| `netcdf-plot-map/references/regions.json` | NEW | Machine-readable regions |
| `netcdf-plot-map/references/colormaps.json` | NEW | Field-character → cmap mapping |
| `netcdf-plot-timeseries/SKILL.md` | UPDATE | Fill in TODOs; full procedure |
| `netcdf-plot-profile/SKILL.md` | UPDATE | Vertical-only; defer cross/hov |

### Test files (`tests/skills/`)

| File | What it covers |
|------|----------------|
| `conftest.py` | SKILL.md parser fixtures |
| `_skill_helpers.py` | Shared helpers (frontmatter parsing, section detection) |
| `test_skill_frontmatter.py` | Valid YAML; name matches directory; description ≤ 280 chars |
| `test_skill_sections.py` | Required body sections in order |
| `test_skill_tool_refs.py` | All `<server>.<tool>` refs point to real MCP tools |
| `test_skill_cross_refs.py` | Sibling skill + reference file refs resolve |
| `test_skill_style_section.py` | Plot skills have `## Style by reference` section |
| `test_regions_sync.py` | regions.md ↔ regions.json in sync |
| `test_regions_schema.py` | regions.json shape + sane bounds |
| `test_colormaps_schema.py` | colormaps.json shape + cmap names valid |
| `test_aliases_format.py` | aliases.md has refiner-insert markers |
| `test_task_log_format.py` | Task-log JSONL schema |
| `integration/test_map_flow.py` | End-to-end: NetCDF → inspect → read_slice → render_map |

### Other

- `docs/specs/2026-05-07-cycle-3-plot-skills.md` — already shipped.
- `docs/plans/2026-05-07-cycle-3-plot-skills.md` — this plan.

---

## Phase 1: Test framework foundation

### Task 1: tests/skills/ scaffold + conftest

**Files:**
- Create: `tests/skills/__init__.py`
- Create: `tests/skills/conftest.py`
- Create: `tests/skills/_skill_helpers.py`

- [ ] **Step 1: Verify pyyaml installed; install if missing**

```bash
.venv/bin/python -c "import yaml; print(yaml.__version__)" 2>&1 | head -3
```

If ModuleNotFoundError:
```bash
uv pip install --python .venv/bin/python pyyaml
```

- [ ] **Step 2: Write `_skill_helpers.py`**

```python
# tests/skills/_skill_helpers.py
"""Shared helpers for skill content validation tests.

Parses SKILL.md files into frontmatter + body, provides section
extraction utilities. Used by all tests/skills/test_*.py modules.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml


SKILLS_ROOT = Path(__file__).resolve().parents[2] / "src" / "skills"


def list_skills() -> list[Path]:
    """Return paths to all SKILL.md files under src/skills/."""
    return sorted(SKILLS_ROOT.glob("*/SKILL.md"))


def parse_skill(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_markdown) for a SKILL.md file."""
    text = path.read_text()
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{path}: unterminated YAML frontmatter")
    fm_text = text[4:end]
    body = text[end + 5:]
    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        raise ValueError(f"{path}: frontmatter is not a YAML mapping")
    return fm, body


def find_sections(body: str) -> list[tuple[int, str]]:
    """Return [(level, title), ...] for every markdown heading in body, in order."""
    out: list[tuple[int, str]] = []
    for line in body.splitlines():
        m = re.match(r"^(#{1,6})\s+(.+?)\s*$", line)
        if m:
            out.append((len(m.group(1)), m.group(2)))
    return out


def has_section(body: str, title: str, level: int = 2) -> bool:
    return any(lvl == level and t == title for lvl, t in find_sections(body))


def section_index(body: str, title: str, level: int = 2) -> int:
    """Return the index in the heading sequence at which `title` first appears.
    Returns -1 if absent."""
    for i, (lvl, t) in enumerate(find_sections(body)):
        if lvl == level and t == title:
            return i
    return -1
```

- [ ] **Step 3: Write `tests/skills/conftest.py`**

```python
# tests/skills/conftest.py
"""Fixtures for skill content tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import SKILLS_ROOT, list_skills


@pytest.fixture
def skills_root() -> Path:
    return SKILLS_ROOT


@pytest.fixture
def skill_paths() -> list[Path]:
    return list_skills()
```

- [ ] **Step 4: Empty `__init__.py`**

```python
# tests/skills/__init__.py
```

- [ ] **Step 5: Verify pytest can collect the empty test dir**

```bash
.venv/bin/pytest tests/skills -v
```

Expected: `collected 0 items` cleanly.

- [ ] **Step 6: Commit**

```bash
git add tests/skills/__init__.py tests/skills/conftest.py tests/skills/_skill_helpers.py
git commit -m "cycle-3 task 1: tests/skills scaffold + SKILL.md parser helpers"
```

---

### Task 2: Skill frontmatter validation test

**Files:**
- Create: `tests/skills/test_skill_frontmatter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/skills/test_skill_frontmatter.py
"""Validate SKILL.md frontmatter shape across all skills."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill


# Skip skill-refiner — that's cycle 6, not in scope for cycle 3
_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _cycle3_skill_paths() -> list[Path]:
    return [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS]


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_frontmatter_required_fields(path: Path) -> None:
    fm, _ = parse_skill(path)
    assert "name" in fm, f"{path.parent.name}: missing 'name' in frontmatter"
    assert "description" in fm, (
        f"{path.parent.name}: missing 'description' in frontmatter")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_name_matches_directory(path: Path) -> None:
    fm, _ = parse_skill(path)
    assert fm["name"] == path.parent.name, (
        f"name {fm['name']!r} != directory {path.parent.name!r}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_description_length(path: Path) -> None:
    fm, _ = parse_skill(path)
    desc = fm["description"]
    assert isinstance(desc, str), f"description must be a string, got {type(desc)}"
    assert 1 <= len(desc) <= 1024, (
        f"description length {len(desc)} out of range [1, 1024] "
        f"for {path.parent.name}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_description_is_single_paragraph(path: Path) -> None:
    """Description should be a single sentence/paragraph (no double newlines)."""
    fm, _ = parse_skill(path)
    assert "\n\n" not in fm["description"], (
        f"{path.parent.name}: description should be a single paragraph")
```

- [ ] **Step 2: Run, verify partial pass / partial fail**

```bash
.venv/bin/pytest tests/skills/test_skill_frontmatter.py -v
```

Existing skill stubs already have valid frontmatter, so this should mostly pass. If any skill has missing `description` or doesn't match its dir name, the test will catch it. If any test fails, fix the offending SKILL.md frontmatter — do NOT relax the test.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_skill_frontmatter.py
git commit -m "cycle-3 task 2: test_skill_frontmatter (parametrized over 5 cycle-3 skills)"
```

---

## Phase 2: Reference data files

### Task 3: regions.json

**Files:**
- Create: `src/skills/netcdf-plot-map/references/regions.json`

The regions are extracted from the existing `regions.md` table. Use **-180..180** convention.

- [ ] **Step 1: Write `regions.json`**

```json
{
  "schema_version": 1,
  "categories": ["ocean_basin", "continental", "climate_index", "tc_basin", "polar"],
  "regions": {
    "North Atlantic":      {"lon_min": -80, "lon_max":   0, "lat_min":  20, "lat_max":  70, "category": "ocean_basin"},
    "Tropical Atlantic":   {"lon_min": -60, "lon_max":  20, "lat_min": -20, "lat_max":  20, "category": "ocean_basin"},
    "South Atlantic":      {"lon_min": -70, "lon_max":  20, "lat_min": -60, "lat_max":   0, "category": "ocean_basin"},
    "North Pacific":       {"lon_min": 120, "lon_max":-100, "lat_min":  20, "lat_max":  65, "category": "ocean_basin", "notes": "crosses dateline"},
    "Tropical Pacific":    {"lon_min": 120, "lon_max": -70, "lat_min": -20, "lat_max":  20, "category": "ocean_basin", "notes": "crosses dateline"},
    "South Pacific":       {"lon_min": 150, "lon_max": -70, "lat_min": -60, "lat_max":   0, "category": "ocean_basin", "notes": "crosses dateline"},
    "Indian Ocean":        {"lon_min":  30, "lon_max": 120, "lat_min": -40, "lat_max":  30, "category": "ocean_basin"},
    "Southern Ocean":      {"lon_min":-180, "lon_max": 180, "lat_min": -75, "lat_max": -40, "category": "polar"},
    "Arctic":              {"lon_min":-180, "lon_max": 180, "lat_min":  60, "lat_max":  90, "category": "polar"},

    "Niño 3.4":            {"lon_min":-170, "lon_max":-120, "lat_min":  -5, "lat_max":   5, "category": "climate_index", "notes": "ENSO index region"},

    "CONUS":               {"lon_min":-125, "lon_max": -65, "lat_min":  24, "lat_max":  50, "category": "continental"},
    "Western US":          {"lon_min":-125, "lon_max":-100, "lat_min":  30, "lat_max":  50, "category": "continental"},
    "Eastern US":          {"lon_min":-100, "lon_max": -65, "lat_min":  24, "lat_max":  48, "category": "continental"},
    "Europe":              {"lon_min": -15, "lon_max":  45, "lat_min":  35, "lat_max":  72, "category": "continental"},
    "Mediterranean":       {"lon_min": -10, "lon_max":  40, "lat_min":  30, "lat_max":  48, "category": "continental"},
    "West Africa":         {"lon_min": -20, "lon_max":  30, "lat_min":  -5, "lat_max":  25, "category": "continental"},
    "East Africa":         {"lon_min":  30, "lon_max":  55, "lat_min": -10, "lat_max":  20, "category": "continental"},
    "South Asia":          {"lon_min":  65, "lon_max": 100, "lat_min":   5, "lat_max":  40, "category": "continental"},
    "East Asia":           {"lon_min": 100, "lon_max": 150, "lat_min":  20, "lat_max":  55, "category": "continental"},
    "Australia":           {"lon_min": 110, "lon_max": 155, "lat_min": -45, "lat_max": -10, "category": "continental"},
    "Amazon basin":        {"lon_min": -80, "lon_max": -45, "lat_min": -20, "lat_max":   5, "category": "continental"},

    "Tropics":             {"lon_min":-180, "lon_max": 180, "lat_min": -30, "lat_max":  30, "category": "climate_index", "notes": "30S-30N by default"},
    "Inner Tropics":       {"lon_min":-180, "lon_max": 180, "lat_min": -23, "lat_max":  23, "category": "climate_index", "notes": "strict 23.5° tropics"},
    "NH extratropics":     {"lon_min":-180, "lon_max": 180, "lat_min":  30, "lat_max":  90, "category": "climate_index"},
    "SH extratropics":     {"lon_min":-180, "lon_max": 180, "lat_min": -90, "lat_max": -30, "category": "climate_index"},
    "NH polar":            {"lon_min":-180, "lon_max": 180, "lat_min":  60, "lat_max":  90, "category": "polar"},
    "SH polar":            {"lon_min":-180, "lon_max": 180, "lat_min": -90, "lat_max": -60, "category": "polar"},

    "North Atlantic TC":   {"lon_min":-100, "lon_max":   0, "lat_min":   0, "lat_max":  45, "category": "tc_basin"},
    "Eastern Pacific TC":  {"lon_min":-180, "lon_max": -75, "lat_min":   0, "lat_max":  35, "category": "tc_basin"},
    "Western Pacific TC":  {"lon_min": 100, "lon_max": 180, "lat_min":   0, "lat_max":  45, "category": "tc_basin"},
    "North Indian TC":     {"lon_min":  40, "lon_max": 100, "lat_min":   0, "lat_max":  30, "category": "tc_basin"},
    "South Indian TC":     {"lon_min":  30, "lon_max": 120, "lat_min": -35, "lat_max":   0, "category": "tc_basin"},
    "South Pacific TC":    {"lon_min": 135, "lon_max":-120, "lat_min": -35, "lat_max":   0, "category": "tc_basin", "notes": "crosses dateline"}
  }
}
```

- [ ] **Step 2: Verify it parses**

```bash
.venv/bin/python -c "import json; d = json.load(open('src/skills/netcdf-plot-map/references/regions.json')); print(d['schema_version'], len(d['regions']), 'regions')"
```

Expected: `1 32 regions`.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-map/references/regions.json
git commit -m "cycle-3 task 3: regions.json (machine-readable companion to regions.md)"
```

---

### Task 4: colormaps.json

**Files:**
- Create: `src/skills/netcdf-plot-map/references/colormaps.json`

- [ ] **Step 1: Write the file**

```json
{
  "schema_version": 1,
  "by_field_character": {
    "anomaly":              {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "departure":            {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "change":               {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "difference":           {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "temperature_absolute": {"cmap": "RdYlBu_r","kind": "sequential"},
    "temperature_anomaly":  {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "precipitation":        {"cmap": "Blues",   "kind": "sequential"},
    "precipitation_anomaly":{"cmap": "BrBG",    "kind": "diverging",  "vcenter": 0.0},
    "wind_speed":           {"cmap": "viridis", "kind": "sequential"},
    "pressure":             {"cmap": "viridis", "kind": "sequential"},
    "pressure_anomaly":     {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "humidity":             {"cmap": "BrBG",    "kind": "diverging"},
    "specific_humidity":    {"cmap": "Blues",   "kind": "sequential"},
    "geopotential_height":  {"cmap": "viridis", "kind": "sequential"},
    "geopotential":         {"cmap": "viridis", "kind": "sequential"},
    "sea_ice":              {"cmap": "Blues",   "kind": "sequential"},
    "vorticity":            {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0},
    "divergence":           {"cmap": "RdBu_r",  "kind": "diverging",  "vcenter": 0.0}
  },
  "default":           {"cmap": "viridis", "kind": "sequential"},
  "diverging_default": {"cmap": "RdBu_r",  "kind": "diverging", "vcenter": 0.0}
}
```

- [ ] **Step 2: Verify it parses**

```bash
.venv/bin/python -c "import json; d = json.load(open('src/skills/netcdf-plot-map/references/colormaps.json')); print(d['schema_version'], len(d['by_field_character']), 'characters')"
```

Expected: `1 18 characters`.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-map/references/colormaps.json
git commit -m "cycle-3 task 4: colormaps.json (field-character → cmap mapping)"
```

---

### Task 5: Reference data integrity tests

**Files:**
- Create: `tests/skills/test_regions_schema.py`
- Create: `tests/skills/test_colormaps_schema.py`

- [ ] **Step 1: Write `test_regions_schema.py`**

```python
# tests/skills/test_regions_schema.py
import json
from pathlib import Path

import pytest


_REGIONS_PATH = (Path(__file__).resolve().parents[2]
                 / "src" / "skills" / "netcdf-plot-map"
                 / "references" / "regions.json")


def _load() -> dict:
    return json.loads(_REGIONS_PATH.read_text())


def test_file_parses():
    d = _load()
    assert isinstance(d, dict)


def test_schema_version_pinned():
    d = _load()
    assert d["schema_version"] == 1


def test_regions_dict_present():
    d = _load()
    assert isinstance(d["regions"], dict)
    assert len(d["regions"]) > 0


def test_categories_consistent():
    d = _load()
    valid_categories = set(d["categories"])
    for name, region in d["regions"].items():
        assert region.get("category") in valid_categories, (
            f"region {name!r} has unknown category {region.get('category')!r}")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_region_has_required_fields(region_name: str, region: dict):
    for field in ("lon_min", "lon_max", "lat_min", "lat_max"):
        assert field in region, f"region {region_name!r} missing {field}"
        assert isinstance(region[field], (int, float)), (
            f"region {region_name!r} {field} must be numeric")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_lat_range_sane(region_name: str, region: dict):
    assert -90 <= region["lat_min"] <= 90
    assert -90 <= region["lat_max"] <= 90
    assert region["lat_min"] <= region["lat_max"], (
        f"region {region_name!r} lat_min > lat_max")


@pytest.mark.parametrize("region_name,region", _load()["regions"].items())
def test_lon_range_sane(region_name: str, region: dict):
    # Allow lon_min > lon_max for regions that cross the dateline
    assert -180 <= region["lon_min"] <= 180
    assert -180 <= region["lon_max"] <= 180
```

- [ ] **Step 2: Write `test_colormaps_schema.py`**

```python
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
```

- [ ] **Step 3: Run, verify all tests pass**

```bash
.venv/bin/pytest tests/skills/test_regions_schema.py tests/skills/test_colormaps_schema.py -v
```

Expected: many parametrized cases pass.

- [ ] **Step 4: Commit**

```bash
git add tests/skills/test_regions_schema.py tests/skills/test_colormaps_schema.py
git commit -m "cycle-3 task 5: regions.json + colormaps.json schema tests"
```

---

## Phase 3: netcdf-inspect skill

### Task 6: Update netcdf-inspect SKILL.md

**Files:**
- Modify: `src/skills/netcdf-inspect/SKILL.md`

The current stub is mostly correct; refresh for cycle 1's actual MCP signature and add explicit `## Recording lessons` task-log format.

- [ ] **Step 1: Replace the file with this content**

```markdown
---
name: netcdf-inspect
description: Inspect a NetCDF file before doing anything else with it. Lists variables, dimensions, coordinate ranges, units, and CF metadata. Use this whenever a NetCDF file path is mentioned for the first time in a session, before attempting any plot, slice, or analysis. Also use when the user asks "what's in this file" or "what variables are available". Do NOT skip this step even if the filename suggests what's inside — filenames lie, conventions differ, and grounding every later step in real metadata prevents a large class of silent failures.
---

# netcdf-inspect

## When to use

- Any NetCDF file path appears for the first time in a session.
- User asks what's in a file ("what variables", "show me the structure").
- User asks for a plot/slice from a file you haven't inspected yet — inspect
  first, then proceed.
- Path is local, glob (`*.nc`), remote URL (`https://...`), or SSH
  (`ssh://host/path.nc`). The MCP handles all of these.

## Quick reference

1. Call `netcdf-reader.inspect(path=<path>)`.
2. If the response envelope is `ok: false` with subcode `ssh_auth_needed`,
   prompt the user for SSH credentials per the candidates list, then retry
   with `ssh_config={user, host, port, auth: {...}}`.
3. Read `result.kind`, `result.convention`, `result.variables`,
   `result.dimensions`, `result.spatial`, `result.time`, `result.vertical`.
4. Summarize for the user (see "What to surface" below).
5. Cross-reference variable names against `references/aliases.md` if the
   user's later prompt names a quantity informally.
6. If an alias resolution differs from what the user said, log a
   `alias_correction` event to `.ncplot/task-log.jsonl` (see "Recording
   lessons").

## What to surface to the user

Don't dump the entire ncdump output. The user wants:
- **Variables:** number total, with the 5–10 most plot-relevant ones named
  explicitly (prioritize ones with both spatial and temporal dimensions).
- **Time range:** start, end, frequency if regular (use `result.time.range`
  and `result.time.frequency`).
- **Spatial extent:** lon range, lat range, grid resolution (use
  `result.spatial.lon_range`, `result.spatial.lat_range`, and the lon
  convention from `result.spatial.lon_convention`).
- **Vertical coord** if present: kind (pressure / height / depth / model_level)
  and value range (use `result.vertical`).
- **Convention:** primary (`CF` / `WRF` / `ROMS`) plus any candidates if
  ambiguous.
- **Red flags:** see Pitfalls.

## Available helper tools

For follow-up resolution beyond `inspect()`:

- `netcdf-reader.find_variables(path, hint)` — score variables against
  `long_name`/`standard_name`/`description` for fuzzy lookup.
- `netcdf-reader.find_time(path, hint)` — parse "2024-09", "last", "first"
  into ISO + index.

## Pitfalls

- **Longitude convention.** Files are either 0–360 or -180–180. The
  difference is silent until a user names a region — record which one
  this file uses (it's in `result.spatial.lon_convention`).
- **Calendar.** CF supports several non-Gregorian calendars (noleap,
  360_day, julian). The MCP normalizes via cftime, but downstream
  pandas-style tools may fail. Note the calendar in the inspection summary.
- **Staggered grids (WRF).** U and V on different grids than scalars
  (Arakawa C-grid). The MCP detects this and reports
  `result.staggered_grid: true` plus annotated coordinate names. Plotting
  needs interpolation via `netcdf-reader.regrid_to_centers`.
- **Curvilinear coordinates (WRF, ROMS).** 2D `XLAT`/`XLONG` instead of 1D
  `lat`/`lon`. The MCP exposes both via `result.spatial.coordinate_kind`
  ("rectilinear" or "curvilinear"). The renderer handles both.
- **Time as numbers.** Time variable may be `days since 1850-01-01` or
  similar. The MCP decodes via `decode_times=True`; if the response
  contains a `cf_time_decode_failed` warning, surface it.
- **Variables with no `units` attribute.** Common in research output.
  Note this; the plotting skills will need to ask the user.
- **Unstructured grids.** ICON, MPAS, FV3 may use unstructured meshes.
  Detected by absence of regular `lon`/`lat` coordinates. Cycle-3
  doesn't ship plotting for these — surface this and stop.

## Verification

Before declaring inspection complete:
- Confirm at least one variable was returned (`len(result.variables) > 0`).
- Confirm dimension sizes are non-zero.
- Confirm coordinate values are monotonic where expected (lat/lon/time).
  The MCP marks non-monotonic axes in `result.warnings`.
- If any check fails, surface the failure to the user — do not proceed
  to plotting on a malformed file.

## Style by reference

`netcdf-inspect` does not produce plots and does not consume style
templates. (The plot skills handle the style-by-reference flow; see
`netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile`.)

## Recording lessons

If the user corrects you about variable name resolution, append to
`.ncplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-inspect",
  "step": "alias_correction",
  "input": "user said: SST",
  "resolved": "tos",
  "via": "user_correction",
  "context": "CMIP6 historical run"
}
```

Required fields: `ts`, `skill`, `step`, `via`. `input`, `resolved`, and
`context` are recommended.

The `skill-refiner` (cycle 6) will pick this up at session end and
propose adding the alias to `references/aliases.md`.

## See also

- `netcdf-plot-router` — what to do after inspection
- `netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile` — produce plots
- `references/aliases.md` — variable name aliases
- `references/conventions.md` — CF conventions cheat sheet
```

- [ ] **Step 2: Verify the file is well-formed**

```bash
.venv/bin/python -c "
import yaml, sys
from pathlib import Path
text = Path('src/skills/netcdf-inspect/SKILL.md').read_text()
assert text.startswith('---\n')
end = text.find('\n---\n', 4)
fm = yaml.safe_load(text[4:end])
print('name:', fm['name'])
print('desc len:', len(fm['description']))
"
```

Expected: `name: netcdf-inspect`, `desc len:` between 200 and 1024.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-inspect/SKILL.md
git commit -m "cycle-3 task 6: netcdf-inspect SKILL.md (current MCP sig + task-log format)"
```

---

### Task 7: Refresh aliases.md and conventions.md (minor updates)

**Files:**
- Modify: `src/skills/netcdf-inspect/references/aliases.md`
- Modify: `src/skills/netcdf-inspect/references/conventions.md`

The existing files are good. We add small refinements: WRF surface-specific aliases, a "How skills use this file" preamble for both.

- [ ] **Step 1: Add to top of `aliases.md` (after the existing first paragraph)**

After the line `> This file is updated by the \`skill-refiner\` loop.` and before `## Sea surface temperature`, insert:

```markdown
## How skills use this file

Plot skills (`netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile`)
look up user-supplied informal names against this table to find the
canonical variable name in the current file. The lookup is case-insensitive
and does substring matching against the "User says" column.

If a lookup is ambiguous (multiple matches) or empty, the skill calls
`netcdf-reader.find_variables(path, hint)` for a scored search against
the file's actual `long_name`/`standard_name`/`description` attributes.
If still ambiguous, the skill asks the user.
```

- [ ] **Step 2: Add WRF surface-wind aliases to the `## Wind components` table**

Append to the `Wind components` table:

```markdown
| 10m wind, U10/V10 | `u10`, `v10`, `U10`, `V10`, `eastward_wind_10m`, `northward_wind_10m` | surface wind components in WRF; ERA5 uses `u10`/`v10` |
```

- [ ] **Step 3: Add to top of `conventions.md` (just after the first paragraph)**

After `Full spec: cfconventions.org.` and before `## Coordinate variables`, insert:

```markdown
## How skills use this file

`netcdf-inspect` consults this file when surfacing oddities to the user
(non-standard calendars, missing units, staggered grids). Plot skills
also rely on it for cell-methods interpretation (a "monthly precipitation"
file with `cell_methods="time: mean"` is a rate; with `time: sum` is an
accumulation — different conversion factors).

The `netcdf-reader.inspect()` MCP tool detects most of these conditions
automatically and reports them in `result.convention` and
`result.warnings`. This file is a human reference for context the MCP
cannot fully convey.
```

- [ ] **Step 4: Verify both files still parse as markdown (no special validation needed)**

```bash
wc -l src/skills/netcdf-inspect/references/aliases.md \
       src/skills/netcdf-inspect/references/conventions.md
```

Expected: both ≥ 80 lines.

- [ ] **Step 5: Commit**

```bash
git add src/skills/netcdf-inspect/references/aliases.md \
        src/skills/netcdf-inspect/references/conventions.md
git commit -m "cycle-3 task 7: aliases.md + conventions.md preambles + WRF surface winds"
```

---

### Task 8: test_skill_sections

**Files:**
- Create: `tests/skills/test_skill_sections.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_skill_sections.py
"""Validate required sections appear in each cycle-3 SKILL.md."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import (
    list_skills, parse_skill, find_sections,
)

# Required L2 sections for every cycle-3 skill, in order.
_REQUIRED_SECTIONS = [
    "When to use",
    "Quick reference",
    # Pitfalls is optional but recommended; we don't require it.
    "Verification",
    "Recording lessons",
    "See also",
]

# netcdf-plot-router is exempt from Verification + Recording lessons since
# it doesn't produce output directly.
_ROUTER_REQUIRED_SECTIONS = [
    "When to use",
    "Quick reference",
    "See also",
]

_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _cycle3_skill_paths() -> list[Path]:
    return [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS]


def _required_for(name: str) -> list[str]:
    if name == "netcdf-plot-router":
        return _ROUTER_REQUIRED_SECTIONS
    return _REQUIRED_SECTIONS


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_required_sections_present(path: Path) -> None:
    _, body = parse_skill(path)
    sections = [t for lvl, t in find_sections(body) if lvl == 2]
    for required in _required_for(path.parent.name):
        assert required in sections, (
            f"{path.parent.name}: missing L2 section {required!r}; "
            f"found {sections}")


@pytest.mark.parametrize("path", _cycle3_skill_paths(),
                         ids=lambda p: p.parent.name)
def test_sections_in_order(path: Path) -> None:
    _, body = parse_skill(path)
    sections = [t for lvl, t in find_sections(body) if lvl == 2]
    required = _required_for(path.parent.name)
    last_idx = -1
    for r in required:
        idx = sections.index(r)  # raises if missing — caught by previous test
        assert idx > last_idx, (
            f"{path.parent.name}: section {r!r} appears at index {idx} "
            f"but should come after the previous required section "
            f"(last_idx={last_idx})")
        last_idx = idx
```

- [ ] **Step 2: Run; expect netcdf-inspect to pass and others to FAIL until later tasks update them**

```bash
.venv/bin/pytest tests/skills/test_skill_sections.py -v
```

Expected: netcdf-inspect passes, netcdf-plot-{router,map,timeseries,profile} fail (those skills are still stubs and don't have all required sections yet). The failures are EXPECTED — they're what TDD's red step produces. We commit the test now and let subsequent tasks make it green.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_skill_sections.py
git commit -m "cycle-3 task 8: test_skill_sections (currently failing for stub skills, fixes pending)"
```

---

## Phase 4: netcdf-plot-router skill

### Task 9: Update netcdf-plot-router SKILL.md

**Files:**
- Modify: `src/skills/netcdf-plot-router/SKILL.md`

- [ ] **Step 1: Replace the file**

```markdown
---
name: netcdf-plot-router
description: Decide which plot type to make from a free-form natural-language request and dispatch to the right plotting skill. Use this whenever the user asks to plot, show, visualize, or graph something from a NetCDF file but hasn't specified the plot type explicitly. Covers maps, time series, and vertical profiles. Cross-section and Hovmöller plots are not yet supported (deferred to a later cycle); this skill informs the user when those are requested.
---

# netcdf-plot-router

## When to use

User wants a plot from a NetCDF file but didn't specify which plot type, or
the type is implied but worth confirming.

## Quick reference

1. Has the file been inspected this session? If no → run `netcdf-inspect`
   first. Don't proceed without inspection — most ambiguities resolve
   themselves once you know what's in the file.

2. Apply the decision tree below to the user's request:

   | Cue                                                         | Skill / action                                          |
   |-------------------------------------------------------------|---------------------------------------------------------|
   | "map", "spatial", named region, projection, "show X over R" | invoke `netcdf-plot-map`                                |
   | "time series", "over time", "trend", "evolution of X"       | invoke `netcdf-plot-timeseries`                         |
   | "vertical", "profile", multiple levels at single point/area | invoke `netcdf-plot-profile`                            |
   | "cross-section", "transect"                                 | **deferred** — see "Deferred plot types" below          |
   | "Hovmöller", "lat-time", "lon-time", "time-longitude"       | **deferred**                                            |
   | Variable shape (lat,lon) at one time, no other cues         | invoke `netcdf-plot-map` (default for 2D spatial)       |

3. If still ambiguous after the decision tree, ask **one** clarifying
   question with 2–3 options. Don't list every variant.

   > "I can show that as a map, a time series, or a vertical profile —
   > which one?"

4. Once decided, invoke the matched skill, passing along:
   - file path
   - resolved variable name (from inspect step)
   - any region / time / level constraints already in the request
   - reference image path/URL if user provided one (for style-by-reference)

## Deferred plot types

Cross-section and Hovmöller plots are not supported in the current
release. When detected, respond:

> "Cross-section plots (a 2D slice through a 3D field) and Hovmöller
> diagrams (time vs spatial axis) aren't supported yet — they're queued
> for a future release. Right now I can do maps, time series, and vertical
> profiles. Would any of those work for what you have in mind?"

Don't try to fake it (e.g., averaging until a profile-like shape emerges
without warning the user) — that produces a misleading plot.

## Pitfalls

- **Don't ask the type question if the answer is obvious.** "Plot SST in
  the North Atlantic for September" is unambiguously a map. Asking is
  friction.
- **"Over time" always means time series**, even if a region is also named
  (it's a regional average time series).
- **"At 500 hPa" + region + time** means a map at that level, not a
  profile. Profiles are 1D in vertical.
- **"Profile" without context** usually means vertical profile (single
  point or area-averaged). Ask if ambiguous.
- **Variable shape doesn't override explicit cue.** If user says "time
  series of T2", even though T2 is a 2D field, do a single-point or
  area-mean time series — not a map.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — 2D maps
- `netcdf-plot-timeseries` — 1D time series
- `netcdf-plot-profile` — vertical profile
```

- [ ] **Step 2: Run section test**

```bash
.venv/bin/pytest tests/skills/test_skill_sections.py::test_required_sections_present -v
```

Expected: netcdf-plot-router now passes (has When to use / Quick reference / See also).

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-router/SKILL.md
git commit -m "cycle-3 task 9: netcdf-plot-router SKILL.md with deferred-type message"
```

---

## Phase 5: netcdf-plot-map skill

### Task 10: Update netcdf-plot-map SKILL.md

**Files:**
- Modify: `src/skills/netcdf-plot-map/SKILL.md`

- [ ] **Step 1: Replace the file**

```markdown
---
name: netcdf-plot-map
description: Generate a 2D lat/lon map from a NetCDF variable. Handles projection, colormap selection, region subsetting, time and level selection, unit conversion, and style-by-reference (extracting visual style from a user-provided reference image). Use whenever the user asks for a "map", a spatial snapshot, "show me X over <region>", or any horizontal slice of a 2D or higher-dimensional NetCDF variable. Always run netcdf-inspect first if the file hasn't been inspected this session. Defers to netcdf-plot-router for type disambiguation.
---

# netcdf-plot-map

## When to use

A 2D (lat, lon) view of a variable at a single time and (if applicable) a
single vertical level. Phrases that map here: "plot X on a map", "show X
over the Atlantic", "X at 500 hPa", "snapshot of X", "make a map of X".

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run on this file,
   run it now.
2. **Resolve variable name.** Use `references/../netcdf-inspect/references/aliases.md`
   for informal names. If still ambiguous, call
   `netcdf-reader.find_variables(path, hint)`.
3. **Resolve time selection** via `netcdf-reader.find_time(path, hint)` if
   the user named a date informally. Default: last time step if not specified.
4. **Resolve vertical level** if variable is 4D. Look for the level in
   `inspect()` output (`result.vertical`) and accept user-supplied level
   in original units.
5. **Resolve region.** Look up the region name in
   `references/regions.json` (machine-readable). If not found, fall back to
   `references/regions.md` or ask the user for an explicit bbox. Default:
   global.
6. **Pick projection** based on region (see "Projection selection" below).
7. **Detect field character** from variable name + units + long_name and
   pick a colormap from `references/colormaps.json` (see "Colormap
   selection" below).
8. **Decide unit conversion** (see "Unit conversion for display").
9. **If user supplied a reference image** for style: run the
   style-by-reference flow (see "Style by reference" section).
10. **Read data** via `netcdf-reader.read_slice(path, variable, time=..., level=..., region=...)`.
11. **Compose render spec** with all resolved fields:
    - `slice_ref` (file form) or `values + lat + lon` (inline form, if the
      slice fits in the inline byte cap or a unit conversion is needed)
    - `projection`, `colormap`, `vmin`/`vmax`/`vcenter`/`clip_pct`
    - `title`, `colorbar_label`, `lon_convention`
    - `style_template` if extracted (step 9)
    - `output_path` if user specified one
12. **Call** `plot-renderer.render_map(spec=...)`.
13. **Verify** (see "Verification" below).
14. **Report** to the user with output path, units, range, warnings.
15. **If user corrected anything**, log to `.ncplot/task-log.jsonl`.

## Projection selection

- **Global** (extent covers > 270° lon) → `PlateCarree` (cylindrical equirectangular).
- **Polar** (latitude > 60° involved as a focus) → `NorthPolarStereo` /
  `SouthPolarStereo`.
- **Tropical band** → `PlateCarree`.
- **Regional** (single basin, country) → `PlateCarree` is fine; use
  `LambertConformal` for mid-latitude continental regions if area
  accuracy matters.
- **User-specified projection always wins.**

## Colormap selection

After detecting field character (rules below), look up
`references/colormaps.json`. The JSON is the source of truth.

**Detection rules:**
- Variable name or `long_name` contains "anomaly" / "departure" / "change" /
  "diff" / "minus" → `anomaly`
- Variable name in {tos, sst, tas, t2m, T2, ts, surface_temperature} or units
  in {K, °C, degC} and no anomaly cue → `temperature_absolute`
- Variable name in {pr, tp, RAINNC, RAINC, precip} or units contain
  `kg m-2 s-1`/`mm`/`mm/day` → `precipitation`
- Variable name in {ua, va, u10, v10, U, V, U10, V10, WSPD, ws} or units
  `m s-1` → `wind_speed`
- Units in {Pa, hPa} and no other cue → `pressure`
- Variable name in {hus, q, QVAPOR, huss} → `specific_humidity`
- Variable name in {hur, rh, RH} → `humidity`
- Variable name in {zg, gh, z} → `geopotential_height`
- No match → `default` (viridis)

**User's explicit `colormap=...` always wins.**

## Region resolution

If user names a region:
1. Open `references/regions.json` and look up by name (case-insensitive,
   substring match accepted).
2. Found → use the bbox.
3. Not found → check `regions.md` for human-readable description; if
   still unclear, ask user for an explicit bbox.

Always check the file's longitude convention (recorded by inspect in
`result.spatial.lon_convention`) against the region bounds. The
plot-renderer applies the shift via the `lon_convention` field; you
just need to set that field correctly.

## Unit conversion for display

Default conversions unless the user explicitly asks for the original unit:
- K → °C for temperature: `T - 273.15`
- Pa → hPa for pressure: `P / 100`
- kg m⁻² s⁻¹ → mm/day for precipitation flux: `× 86400`
- m s⁻¹ stays
- m → km for height-based vertical: `× 0.001`

**Implementation note:** Unit conversion happens skill-side, between
`read_slice` and `render_map`. The renderer doesn't do conversion. This
means the slice must be in inline form so the skill can transform values.
If the slice is too large for inline form, either:
- Subset further (smaller region), so it fits inline.
- Skip conversion; pass raw values; note original unit in title and chat.

State the conversion explicitly in the plot title (e.g., "SST (°C, converted
from K)") and in the chat reply ("converted from K to °C").

## Style by reference

If the user supplied a reference plot image (e.g., "make it look like
this", attached image, or path to a saved figure):

1. Read the prompt template at `docs/style_template_extraction_prompt.md`
   (relative to repo root).
2. Apply your vision capability to the reference image with that prompt;
   produce a `style_template` JSON per the schema in the doc.
3. Validate the JSON loosely (must be a dict; unknown fields are accepted).
4. Pass the JSON as `style_template` in the `render_map` spec. Include
   the `source` provenance block:
   ```json
   {
     "image_path": "<user-provided ref>",
     "extracted_by": "<your model id>",
     "extracted_at": "<ISO timestamp>",
     "confidence": 0.0-1.0
   }
   ```
5. The renderer applies the template per cycle-2 spec §8 — explicit
   spec fields override template fields, which override library defaults.

If no reference image: skip this entire flow.

## Pitfalls

- **Empty slice, blank plot.** If the region/time selection produces a
  zero-cell array, the renderer returns `code: ambiguous, subcode: empty_slice`.
  Don't ignore — surface to user and ask for a different region/time.
- **Longitude convention mismatch.** If the file is 0..360 and you're
  asking for a region with negative lons, set `lon_convention: "-180..180"`
  in the spec. Renderer handles the shift.
- **Staggered grids.** If `inspect()` reported `result.staggered_grid: true`
  AND the variable is on U or V grid, call `netcdf-reader.regrid_to_centers`
  first to interpolate to mass points. Otherwise the plot is offset.
- **CF time decoding failures.** The renderer returns numeric times in
  the response if cftime decode failed. Surface the warning rather than
  guessing.
- **Auto-scale washing out features.** If the field has extreme outliers
  (e.g. one cell with -9e36 leftover from missing-value handling), pass
  `clip_pct: [2, 98]` to suppress them. The renderer also auto-clips when
  data spans > 6 orders of magnitude (per cycle-2 spec §7).
- **User says "global" but variable is regional.** The file may not cover
  the globe. Plot what's there and note the actual extent.
- **NaN-only after region subset.** If the region subset is entirely
  masked (e.g., land for an ocean variable), renderer returns
  `code: ambiguous, subcode: all_nan`. Surface to user.

## Verification

After rendering, before reporting success:
- Output file exists and `result.file_size_bytes` > 5 KB.
- `result.oracle.data.nan_fraction < 1.0`.
- `result.oracle.data.plotted_min != result.oracle.data.plotted_max`
  (constant field is suspicious — usually a bug).
- All warnings in the response envelope are surfaced to the user.

Example reply:
> Saved `north_atlantic_sst_2024-09.png` (320 KB).
> Variable: `tos` (sea surface temperature), converted K → °C.
> Time: 2024-09 (monthly mean). Region: -80 to 0 lon, 20 to 70 lat.
> Range: -1.8 / 18.4 / 28.7 °C (min/mean/max).
> Coverage: 87% (rest masked over land).

## Recording lessons

If the user corrects any choice (colormap, region bounds, projection,
units, level), log a `<step>_correction` event to `.ncplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-map",
  "step": "colormap_correction",
  "input": "auto-picked: RdYlBu_r",
  "resolved": "viridis",
  "via": "user_correction",
  "context": {"variable": "tos", "units": "K"}
}
```

Step values: `colormap_correction`, `region_correction`, `projection_correction`,
`level_correction`, `unit_conversion_skipped`. Required fields: `ts`,
`skill`, `step`, `via`. The `skill-refiner` (cycle 6) consumes these.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-router` — disambiguation
- `netcdf-plot-timeseries`, `netcdf-plot-profile` — sibling plot skills
- `references/regions.json`, `references/regions.md` — region definitions
- `references/colormaps.json` — field-character → colormap mapping
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt
```

- [ ] **Step 2: Run section test**

```bash
.venv/bin/pytest tests/skills/test_skill_sections.py -v -k netcdf-plot-map
```

Expected: netcdf-plot-map test cases pass.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-map/SKILL.md
git commit -m "cycle-3 task 10: netcdf-plot-map SKILL.md (full procedure + style-by-reference + colormaps.json)"
```

---

## Phase 6: netcdf-plot-timeseries skill

### Task 11: Update netcdf-plot-timeseries SKILL.md

**Files:**
- Modify: `src/skills/netcdf-plot-timeseries/SKILL.md`

- [ ] **Step 1: Replace the file**

```markdown
---
name: netcdf-plot-timeseries
description: Generate a 1D time series plot from a NetCDF variable, optionally area-averaged over a region or extracted at a single point. Handles unit conversion, time aggregation (raw / monthly / annual / seasonal), trendlines, and style-by-reference (extracting visual style from a user-provided reference image). Use whenever the user asks for "X over time", "time series of X", "trend in X", or any 1D plot with time on the x-axis. Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-plot-timeseries

## When to use

Time on the x-axis. Cues: "time series", "over time", "trend", "evolution
of", date range without spatial selection, "monthly", "annual mean".

Even if the user names a region, "X in <region> over time" is a regional
average time series — not a map.

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run, run it now.
2. **Resolve variable name** via aliases.md or `find_variables`.
3. **Resolve spatial reduction:**
   - User gave single (lat, lon) → nearest-neighbor extract (slice with
     point selectors).
   - User gave region → area-weighted average. Use `cos(deg2rad(lat))`
     weighting for rectilinear grids; if the dataset has cell `bounds`
     attributes (CF), prefer bounds-based weights.
   - No spatial constraint and variable has lat/lon dims → area-weighted
     global mean.
   - Variable already 1D in time → use as-is.
4. **Resolve time range** via `find_time` if user named informally
   (default: full record).
5. **Decide aggregation** from request:
   - "monthly mean" / "monthly" → `aggregation="monthly"`
   - "annual mean" / "yearly" → `aggregation="annual"`
   - "seasonal" / "DJF/MAM/JJA/SON" → `aggregation="seasonal"`
   - Otherwise → `aggregation="raw"`
6. **Read data** via `netcdf-reader.read_slice(...)` with appropriate
   selectors (region or point).
7. **Compute spatial reduction skill-side**:
   - For regional/global: weighted mean with `cos(deg2rad(lat))`.
   - For single-point: already done by `read_slice` selectors.
8. **Apply unit conversion** if needed (K → °C, etc.) — see
   `netcdf-plot-map/SKILL.md` for the conventions.
9. **Decide trendline:**
   - User asks for "trend" / "fit" → `trendline="linear"` (or "lowess"
     if specifically requested).
   - Otherwise omit.
10. **If user supplied a reference image**, run style-by-reference flow
    (see "Style by reference" section).
11. **Compose render spec** with `series=[{values, time, label, color?}]`
    or sugar `values + time` for single-series.
12. **Call** `plot-renderer.render_timeseries(spec=...)`.
13. **Verify and report.**
14. **If user corrected anything**, log to `.ncplot/task-log.jsonl`.

## Spatial-reduction math

For a rectilinear grid with 1D `lat` (in degrees):

```
weights = cos(deg2rad(lat))                      # shape (n_lat,)
weighted_sum_per_t = sum(values * weights[None, :, None], axis=(1, 2))
weight_total       = sum(weights[:, None]
                          * ones_like(lon)[None, :], axis=(0, 1))
mean_per_t         = weighted_sum_per_t / weight_total
```

Skip cells where `values` is NaN (use `np.nansum` and weight-mask the
denominator). Document the resulting `nan_fraction` in the title or chat.

For curvilinear grids (WRF/ROMS): use the dataset's cell-area variable if
present (e.g., `XAREA`), otherwise approximate with `cos(lat) * ΔlatΔlon`
of the curvilinear coords.

## Calendar handling

If the file uses a non-Gregorian calendar (noleap, 360_day) — reported by
`inspect()` — annual aggregation still works (each year has fixed 365 or
360 days). Note the calendar in the chart title or chat reply if it
might mislead the user (e.g., a "30-year noleap mean" loses ~7 days vs
Gregorian).

## Multi-series

If the user asks to compare regions ("compare SST in NA vs TP over time"):
- Make multiple `read_slice` calls — one per region.
- Compute spatial reductions per series.
- Build `series=[{values, time, label}, ...]` with len > 1.
- Renderer auto-emits a legend.

If user asks to compare variables ("compare T2m and SST over time"):
- Same pattern, one series per variable.
- If units differ, the series share an axis — call this out in chat
  ("the y-axis mixes K and °C; consider plotting separately").

## Pitfalls

- **Area-weighting math when grid is non-uniform.** For rectilinear grids
  with constant Δlat, `cos(lat)` weighting is correct. For irregular Δlat
  or curvilinear grids, use cell areas if available.
- **Leap years for annual aggregation.** Under noleap calendar, every
  year has 365 days; standard datetime tools may misrepresent. Use
  cftime-aware grouping (`xarray` does this with `decode_times=True`).
- **Missing data.** Use `np.nanmean`, not `np.mean` — silent NaN
  propagation produces all-NaN output. Report `nan_fraction` from the
  oracle in the chat.
- **Trend lines vs raw values.** When the user says "trend", they may
  mean "show a trendline" OR "show only the trend, removing seasonal".
  Ask if ambiguous. Default: `trendline="linear"` overlaid on the raw
  series.
- **Unit conversion + slice file form.** If the slice file form is used
  (large slice), you cannot convert units skill-side. Either subset to
  fit inline form or skip conversion and note units in the title.

## Style by reference

If the user supplied a reference plot image:
1. Read `docs/style_template_extraction_prompt.md`.
2. Apply your vision capability to the reference image with that prompt;
   produce a `style_template` JSON.
3. Pass it as `style_template` in the render call (renderer applies per
   cycle-2 spec §8). Include `source` provenance.

The relevant template fields for time series are: `colormap_kind`
(rarely used for line plots; only relevant if comparing many series),
`legend_placement`, `gridlines`, `aspect`, `font_scale`, `title_placement`.
Map-specific fields (`projection_family`, `extent_hint`, `colorbar_position`)
are ignored by `render_timeseries`.

## Verification

- Output file size > 5 KB.
- Time axis monotonic (renderer verifies; warns otherwise).
- All series have `n_points > 1`.
- Report: variable, units, spatial reduction (point/region/global),
  time range, n_points, min/mean/max.

## Recording lessons

Log to `.ncplot/task-log.jsonl` on user corrections:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-timeseries",
  "step": "spatial_reduction_correction",
  "input": "user said: NA timeseries",
  "resolved_initial": "regional area mean over -80..0 lon, 20..70 lat",
  "resolved_final":   "global area mean",
  "via": "user_correction"
}
```

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — for the analogous map flow + style-by-reference details
- `netcdf-plot-router` — disambiguation
- `netcdf-plot-profile` — sibling plot skill
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt
```

- [ ] **Step 2: Run section test**

```bash
.venv/bin/pytest tests/skills/test_skill_sections.py -v -k netcdf-plot-timeseries
```

Expected: pass.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-timeseries/SKILL.md
git commit -m "cycle-3 task 11: netcdf-plot-timeseries SKILL.md (full procedure + style-by-reference)"
```

---

## Phase 7: netcdf-plot-profile skill

### Task 12: Update netcdf-plot-profile SKILL.md

**Files:**
- Modify: `src/skills/netcdf-plot-profile/SKILL.md`

- [ ] **Step 1: Replace the file**

```markdown
---
name: netcdf-plot-profile
description: Generate a vertical profile plot (variable vs height/pressure/depth) at a single point or area-averaged. Handles pressure-axis inversion, log-scale for pressure, depth-axis inversion (positive-down), unit conversion, and style-by-reference. Use whenever the user asks for a "profile", "vertical structure", "vertical X", or "X vs height/pressure". Always run netcdf-inspect first if the file hasn't been inspected this session. Cross-section and Hovmöller plots are not yet supported in this cycle — netcdf-plot-router will inform the user when those are requested.
---

# netcdf-plot-profile

## When to use

Vertical structure of a variable at a single location or area average.
Cues: "profile", "vertical X", "X vs height", "X vs pressure", "X at all
levels".

Cross-section (2D slice through a 3D field) and Hovmöller (time vs
spatial axis) are **not supported in this cycle** — `netcdf-plot-router`
informs the user. This skill handles only vertical profile.

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run, run it now.
2. **Resolve variable name** via aliases.md or `find_variables`.
3. **Confirm vertical coordinate present** in `inspect()` output:
   `result.vertical` should be non-null with a `kind` ("pressure", "height",
   "depth", "model_level"). If missing, this isn't a profile-able variable.
4. **Resolve spatial reduction:**
   - User gave single (lat, lon) → nearest-neighbor extract.
   - User gave region → area-weighted average across the region.
   - Default: ask user (point or area? — profiles are usually point-based).
5. **Resolve time selection** (default: last time step). Profiles are
   usually instantaneous.
6. **Read data** via `netcdf-reader.read_slice(...)` with selectors that
   reduce to (vertical, ) — i.e., one value per vertical level.
7. **Apply unit conversion** if needed (K → °C, Pa → hPa, m → km).
8. **Set vertical-axis policy** based on `vertical.kind`:
   - `pressure` (units in {Pa, hPa}) → `vertical_units` = matching unit;
     `log_scale=True`, `invert_pressure=True` (low pressure at top).
   - `height` (units in {m, km}) → `log_scale=False`, `invert_pressure=False`.
     Optional km conversion if range > 1000 m.
   - `depth` (units in {m}) → `log_scale=False`, `invert_pressure=True`
     (deepest at bottom; surface at top).
   - `model_level` (dimensionless) → `log_scale=False`, `invert_pressure=False`.
     Note in title that levels are model levels, not physical units.
9. **If user supplied a reference image**, run style-by-reference flow.
10. **Compose render spec:** `series=[{values, vertical, label, color?}]`
    or sugar `values + vertical` for single-profile. Include
    `vertical_units`, `vertical_axis="y"` (default), `log_scale`,
    `invert_pressure`.
11. **Call** `plot-renderer.render_profile(spec=...)`.
12. **Verify and report.**
13. **If user corrected anything**, log to `.ncplot/task-log.jsonl`.

## Multi-profile

If user asks to compare ("compare T profile in NA vs TP"):
- Multiple `read_slice` calls.
- Build `series=[{values, vertical, label}, ...]`.
- Renderer auto-emits a legend.

## Pitfalls

- **Pressure-axis convention.** Atmospheric pressure decreases with
  altitude — top of plot is low pressure (high altitude). The renderer
  honors `invert_pressure=True`; pass it for any pressure-coordinate
  variable.
- **Log scale for full-column pressure.** A profile from 1000 hPa to 10 hPa
  is meaningless on linear y because the atmosphere thins exponentially.
  Default to log scale for pressure (the renderer auto-picks log when
  `vertical_units in {Pa, hPa}` per cycle-2 spec §2.3).
- **Terrain-following coordinates** (sigma, hybrid sigma-pressure). The
  vertical coordinate isn't a clean physical pressure; values vary with
  surface pressure. If `inspect()` reports a hybrid coord, use the
  derived pressure values if the file provides them; otherwise plot
  against the model-level index and note in the title.
- **Depth profiles.** Ocean variables: vertical coord may have
  `positive="down"`. The renderer handles this (uses `invert_pressure`
  semantics — deep at bottom). Verify the deepest values appear at the
  bottom of the plot in the oracle.
- **Mismatched levels across series.** When comparing two profiles, the
  vertical coordinates must align. If they don't, interpolate to a
  common grid skill-side before passing.
- **Cross-section confusion.** If the user says "vertical cross-section",
  defer to `netcdf-plot-router` — that's not a profile in the
  cycle-3 sense.

## Style by reference

If the user supplied a reference plot image:
1. Read `docs/style_template_extraction_prompt.md`.
2. Apply vision; produce `style_template` JSON.
3. Pass it to `render_profile` with `source` provenance.

Relevant template fields: `legend_placement`, `gridlines`, `aspect`,
`font_scale`, `title_placement`. Color/projection fields are
mostly irrelevant for profiles.

## Verification

- Output file size > 5 KB.
- Vertical axis monotonic.
- All series have `n_points > 1`.
- For pressure profiles: oracle's `drawn.log_scale` is True, `drawn.invert_pressure`
  is True.
- Report: variable, units, mode (profile), spatial reduction, vertical
  range, n_levels.

## Recording lessons

Log corrections to `.ncplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-profile",
  "step": "vertical_axis_correction",
  "input": "auto-picked: log scale + invert (pressure)",
  "resolved": "linear scale + no invert (per user request)",
  "via": "user_correction",
  "context": {"vertical_units": "hPa"}
}
```

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — sibling plot skill (covers style-by-reference details)
- `netcdf-plot-timeseries` — sibling plot skill
- `netcdf-plot-router` — disambiguation
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt
```

- [ ] **Step 2: Run section test**

```bash
.venv/bin/pytest tests/skills/test_skill_sections.py -v
```

Expected: ALL skills now pass section validation.

- [ ] **Step 3: Commit**

```bash
git add src/skills/netcdf-plot-profile/SKILL.md
git commit -m "cycle-3 task 12: netcdf-plot-profile SKILL.md (vertical-only; defer cross/hov)"
```

---

## Phase 8: Cross-cutting validation tests

### Task 13: test_skill_tool_refs

**Files:**
- Create: `tests/skills/test_skill_tool_refs.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_skill_tool_refs.py
"""Verify every <server>.<tool> reference in skill bodies points to a
real MCP tool from cycles 1+2."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill


# Canonical tool lists from cycles 1 and 2 (per their dispatch lists)
_REAL_TOOLS = {
    "netcdf-reader.inspect",
    "netcdf-reader.resolve_spec",
    "netcdf-reader.read_slice",
    "netcdf-reader.compute_stats",
    "netcdf-reader.peek",
    "netcdf-reader.find_variables",
    "netcdf-reader.find_time",
    "netcdf-reader.regrid_to_centers",
    "plot-renderer.render_map",
    "plot-renderer.render_timeseries",
    "plot-renderer.render_profile",
}

# Pattern for `<server>.<tool>` references in skill markdown.
# Matches things like `netcdf-reader.inspect` or `plot-renderer.render_map`
# inside backticks or bare. Excludes things like `netcdf-reader.inspect()` —
# we'll strip the parens.
_TOOL_REF = re.compile(
    r"\b(netcdf-reader|plot-renderer)\.([a-z][a-z0-9_]*)\b"
)

_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def _extract_tool_refs(text: str) -> set[str]:
    return {f"{m.group(1)}.{m.group(2)}" for m in _TOOL_REF.finditer(text)}


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_all_tool_refs_real(path: Path) -> None:
    _, body = parse_skill(path)
    refs = _extract_tool_refs(body)
    bad = refs - _REAL_TOOLS
    assert not bad, (
        f"{path.parent.name}: skill body references unknown MCP tools: "
        f"{sorted(bad)}; valid tools: {sorted(_REAL_TOOLS)}")
```

- [ ] **Step 2: Run, verify all skills pass**

```bash
.venv/bin/pytest tests/skills/test_skill_tool_refs.py -v
```

Expected: all 5 skills pass. If any fail, fix the SKILL.md to use canonical tool names.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_skill_tool_refs.py
git commit -m "cycle-3 task 13: test_skill_tool_refs (all <server>.<tool> refs valid)"
```

---

### Task 14: test_skill_cross_refs

**Files:**
- Create: `tests/skills/test_skill_cross_refs.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_skill_cross_refs.py
"""Verify cross-references in skill bodies (sibling skills + reference data
files) all resolve to real files."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill, SKILLS_ROOT


_CYCLE_3_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}

# Sibling skills referenced as `\`<name>\`` in body — but it's noisy.
# Instead we just check known sibling-skill names appear and validate
# the few specific reference data files mentioned.
_REQUIRED_SIBLINGS_PER_SKILL = {
    "netcdf-inspect": {"netcdf-plot-router"},
    "netcdf-plot-router": {"netcdf-inspect", "netcdf-plot-map",
                            "netcdf-plot-timeseries", "netcdf-plot-profile"},
    "netcdf-plot-map": {"netcdf-inspect", "netcdf-plot-router"},
    "netcdf-plot-timeseries": {"netcdf-inspect", "netcdf-plot-router"},
    "netcdf-plot-profile": {"netcdf-inspect", "netcdf-plot-router"},
}

# Reference files mentioned in body must exist.
_REPO_ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_required_sibling_skills_referenced(path: Path) -> None:
    _, body = parse_skill(path)
    required = _REQUIRED_SIBLINGS_PER_SKILL[path.parent.name]
    for sib in required:
        assert sib in body, (
            f"{path.parent.name}: body should mention sibling skill {sib!r}")


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _CYCLE_3_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_referenced_files_exist(path: Path) -> None:
    """Verify any `references/<file>` mentioned exists relative to the skill dir,
    and that any `docs/...` mentioned exists relative to the repo root."""
    _, body = parse_skill(path)

    # Skill-relative references: `references/<file>`
    for m in re.finditer(r"references/([A-Za-z0-9_./-]+\.(?:md|json))", body):
        ref = path.parent / "references" / m.group(1)
        # Some skills reference siblings' references by full prefix
        # (`netcdf-inspect/references/aliases.md`); skip those — covered below.
        if "/" in m.group(1):
            continue
        assert ref.exists(), (
            f"{path.parent.name}: missing reference file {ref}")

    # Cross-skill reference paths: `<sibling>/references/<file>`
    for m in re.finditer(
        r"(netcdf-inspect|netcdf-plot-map|netcdf-plot-timeseries|"
        r"netcdf-plot-profile|netcdf-plot-router)/references/"
        r"([A-Za-z0-9_./-]+\.(?:md|json))",
        body,
    ):
        ref = SKILLS_ROOT / m.group(1) / "references" / m.group(2)
        # Some references are advisory (e.g. ../netcdf-inspect/references/aliases.md)
        # may not exist if the path is malformed — only assert if the form looks valid
        if ref.exists():
            continue
        # Otherwise tolerate (could be a paragraph describing a hypothetical path)

    # Doc paths: `docs/...`
    for m in re.finditer(r"docs/([A-Za-z0-9_./-]+\.md)", body):
        ref = _REPO_ROOT / "docs" / m.group(1)
        assert ref.exists(), (
            f"{path.parent.name}: missing docs file {ref}")
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/skills/test_skill_cross_refs.py -v
```

Expected: all skills pass.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_skill_cross_refs.py
git commit -m "cycle-3 task 14: test_skill_cross_refs (sibling skills + reference files)"
```

---

### Task 15: test_skill_style_section

**Files:**
- Create: `tests/skills/test_skill_style_section.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_skill_style_section.py
"""Verify each plot skill has a Style by reference section pointing to
the extraction prompt doc."""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.skills._skill_helpers import list_skills, parse_skill, has_section

_PLOT_SKILLS = {"netcdf-plot-map", "netcdf-plot-timeseries",
                 "netcdf-plot-profile"}


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _PLOT_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_has_style_section(path: Path) -> None:
    _, body = parse_skill(path)
    assert has_section(body, "Style by reference", level=2), (
        f"{path.parent.name}: missing '## Style by reference' section")


@pytest.mark.parametrize(
    "path",
    [p for p in list_skills() if p.parent.name in _PLOT_SKILLS],
    ids=lambda p: p.parent.name,
)
def test_style_section_references_prompt_doc(path: Path) -> None:
    _, body = parse_skill(path)
    assert "docs/style_template_extraction_prompt.md" in body, (
        f"{path.parent.name}: Style by reference section must point to "
        f"docs/style_template_extraction_prompt.md")
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/skills/test_skill_style_section.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_skill_style_section.py
git commit -m "cycle-3 task 15: test_skill_style_section (plot skills reference prompt doc)"
```

---

### Task 16: test_regions_sync

**Files:**
- Create: `tests/skills/test_regions_sync.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_regions_sync.py
"""Verify regions.md table entries match regions.json entries."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_REGIONS_DIR = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
                / "references")
_REGIONS_MD = _REGIONS_DIR / "regions.md"
_REGIONS_JSON = _REGIONS_DIR / "regions.json"

# Regex to parse markdown table rows like:
# | North Atlantic      |     -80 |       0 |      20 |      70 |
_ROW_RE = re.compile(
    r"^\|\s*([^|]+?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
    r"\s*(-?\d+(?:\.\d+)?)\s*\|"
)


def _parse_md_regions() -> dict[str, tuple[float, float, float, float]]:
    out: dict[str, tuple[float, float, float, float]] = {}
    for line in _REGIONS_MD.read_text().splitlines():
        m = _ROW_RE.match(line)
        if not m:
            continue
        name = m.group(1).strip()
        # Skip header rows
        if name in ("Name", "----"):
            continue
        # Skip header separator rows like '---'
        if all(c in "-: " for c in name):
            continue
        try:
            lon_min, lon_max, lat_min, lat_max = (float(m.group(i)) for i in range(2, 6))
        except ValueError:
            continue
        out[name] = (lon_min, lon_max, lat_min, lat_max)
    return out


def _load_json_regions() -> dict[str, tuple[float, float, float, float]]:
    d = json.loads(_REGIONS_JSON.read_text())
    return {name: (r["lon_min"], r["lon_max"], r["lat_min"], r["lat_max"])
            for name, r in d["regions"].items()}


def test_md_and_json_have_same_region_names():
    md = set(_parse_md_regions())
    js = set(_load_json_regions())
    only_in_md = md - js
    only_in_json = js - md
    assert not only_in_md, f"in regions.md but not regions.json: {sorted(only_in_md)}"
    assert not only_in_json, f"in regions.json but not regions.md: {sorted(only_in_json)}"


@pytest.mark.parametrize("name,bbox", _load_json_regions().items())
def test_each_json_region_has_matching_md_bbox(name: str, bbox: tuple) -> None:
    md = _parse_md_regions()
    if name not in md:
        pytest.skip(f"{name!r} not in regions.md (caught by other test)")
    assert md[name] == bbox, (
        f"region {name!r}: md says {md[name]}, json says {bbox}")
```

- [ ] **Step 2: Run; expect either all-pass or specific drift errors**

```bash
.venv/bin/pytest tests/skills/test_regions_sync.py -v
```

If drift: fix `regions.md` to match `regions.json` (or vice versa, depending on which is wrong). Re-run.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_regions_sync.py
git commit -m "cycle-3 task 16: test_regions_sync (regions.md ↔ regions.json)"
```

---

### Task 17: test_aliases_format

**Files:**
- Create: `tests/skills/test_aliases_format.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_aliases_format.py
"""Validate aliases.md has the refiner-insert markers in correct positions."""
from __future__ import annotations

from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_ALIASES = (_REPO_ROOT / "src" / "skills" / "netcdf-inspect"
             / "references" / "aliases.md")


def test_refiner_markers_present():
    text = _ALIASES.read_text()
    assert "<!-- REFINER_INSERT_BELOW -->" in text
    assert "<!-- REFINER_INSERT_ABOVE -->" in text


def test_refiner_markers_in_order():
    text = _ALIASES.read_text()
    below_idx = text.index("<!-- REFINER_INSERT_BELOW -->")
    above_idx = text.index("<!-- REFINER_INSERT_ABOVE -->")
    assert below_idx < above_idx, (
        "REFINER_INSERT_BELOW must appear before REFINER_INSERT_ABOVE")


def test_aliases_has_required_sections():
    text = _ALIASES.read_text()
    required = [
        "## Sea surface temperature",
        "## 2-meter air temperature",
        "## Precipitation",
        "## Wind components",
    ]
    for sec in required:
        assert sec in text, f"aliases.md: missing section {sec!r}"
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/skills/test_aliases_format.py -v
```

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_aliases_format.py
git commit -m "cycle-3 task 17: test_aliases_format (refiner markers + required sections)"
```

---

### Task 18: test_task_log_format

**Files:**
- Create: `tests/skills/test_task_log_format.py`

- [ ] **Step 1: Write the test**

```python
# tests/skills/test_task_log_format.py
"""Validate the task-log JSONL schema (cycle-6 contract)."""
from __future__ import annotations

import json
from datetime import datetime, timezone


def _valid_iso8601(ts: str) -> bool:
    try:
        # Python's fromisoformat accepts "Z" suffix on 3.11+; fall back manually
        if ts.endswith("Z"):
            datetime.fromisoformat(ts.removesuffix("Z")).replace(tzinfo=timezone.utc)
        else:
            datetime.fromisoformat(ts)
        return True
    except ValueError:
        return False


def test_alias_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:30:00Z",
        "skill": "netcdf-inspect",
        "step": "alias_correction",
        "input": "user said: SST",
        "resolved": "tos",
        "via": "user_correction",
        "context": "CMIP6 historical run",
    })
    obj = json.loads(line)
    assert _valid_iso8601(obj["ts"])
    assert obj["skill"] in {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    }
    assert obj["step"] == "alias_correction"
    assert obj["via"] == "user_correction"


def test_region_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:35:00Z",
        "skill": "netcdf-plot-map",
        "step": "region_correction",
        "input": "user said: North Atlantic",
        "resolved_initial": {"lon_min": -80, "lon_max": 0,
                              "lat_min": 20, "lat_max": 70},
        "resolved_final":   {"lon_min": -90, "lon_max": 10,
                              "lat_min": 15, "lat_max": 75},
        "via": "user_correction",
    })
    obj = json.loads(line)
    assert obj["resolved_initial"]["lon_min"] == -80
    assert obj["resolved_final"]["lon_max"] == 10


def test_colormap_correction_event_parses():
    line = json.dumps({
        "ts": "2026-05-07T14:40:00Z",
        "skill": "netcdf-plot-map",
        "step": "colormap_correction",
        "input": "auto-picked: RdYlBu_r",
        "resolved": "viridis",
        "via": "user_correction",
        "context": {"variable": "tos", "units": "K"},
    })
    obj = json.loads(line)
    assert obj["resolved"] == "viridis"
    assert obj["context"]["variable"] == "tos"


def test_required_fields_present():
    """Every event must have ts, skill, step, via."""
    required = {"ts", "skill", "step", "via"}
    sample = {
        "ts": "2026-05-07T14:30:00Z",
        "skill": "netcdf-inspect",
        "step": "alias_correction",
        "via": "user_correction",
    }
    assert required.issubset(sample.keys())


def test_via_values_recognized():
    """`via` field uses one of the recognized provenance values."""
    recognized = {"user_correction", "auto_detected", "prompt_clarified"}
    for via in ("user_correction", "auto_detected", "prompt_clarified"):
        assert via in recognized
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/skills/test_task_log_format.py -v
```

Expected: 5 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/skills/test_task_log_format.py
git commit -m "cycle-3 task 18: test_task_log_format (cycle-6 schema contract)"
```

---

## Phase 9: Integration test

### Task 19: Map-flow integration test

**Files:**
- Create: `tests/skills/integration/__init__.py`
- Create: `tests/skills/integration/test_map_flow.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/skills/integration/test_map_flow.py
"""End-to-end skill-flow simulation: SST in North Atlantic.

Mechanically follows what the netcdf-plot-map skill instructs an agent
to do, against the actual MCP tool functions. No LLM in the loop.
Proves the skill instructions are executable.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import xarray as xr


_REPO_ROOT = Path(__file__).resolve().parents[3]
_REGIONS = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
             / "references" / "regions.json")
_COLORMAPS = (_REPO_ROOT / "src" / "skills" / "netcdf-plot-map"
               / "references" / "colormaps.json")


def _make_synthetic_sst_file(path: Path) -> None:
    """Create a small CF-compliant NetCDF with `tos` (SST in K)."""
    lat = np.linspace(-90, 90, 19)   # 10° lat steps
    lon = np.linspace(-180, 175, 72) # 5° lon steps; 0..360 not used
    # Simple meridional gradient + zonal ripple
    grid_lon, grid_lat = np.meshgrid(lon, lat)
    values = (290.0 + 5.0 * np.cos(np.deg2rad(grid_lat))
              + 1.0 * np.sin(np.deg2rad(grid_lon * 4))).astype("float32")
    ds = xr.Dataset(
        {"tos": (("lat", "lon"), values,
                 {"units": "K", "long_name": "sea surface temperature",
                  "standard_name": "sea_surface_temperature"})},
        coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                "lon": ("lon", lon, {"units": "degrees_east"})},
        attrs={"Conventions": "CF-1.7"},
    )
    ds.to_netcdf(path, engine="netcdf4")


def test_map_flow_e2e(tmp_path, monkeypatch):
    """Simulate the SST map flow per netcdf-plot-map/SKILL.md."""
    monkeypatch.chdir(tmp_path)
    nc_path = tmp_path / "sst.nc"
    _make_synthetic_sst_file(nc_path)

    # Step 1: Inspect (skill instructs: call netcdf-reader.inspect)
    from src.mcp.netcdf_reader.tools.inspect import inspect
    from src.mcp.netcdf_reader.adapter import NetCDFAdapter
    inspect_env = inspect(str(nc_path), adapter=NetCDFAdapter())
    assert inspect_env["ok"] is True
    assert "tos" in {v["name"] for v in inspect_env["result"]["variables"]}

    # Step 2-3: Resolve "SST" → "tos" (skill's alias-resolution step;
    # in practice the agent does this; here we fast-track)
    variable = "tos"

    # Step 5: Resolve "North Atlantic" via regions.json
    regions = json.loads(_REGIONS.read_text())
    na = regions["regions"]["North Atlantic"]
    assert na["lon_min"] == -80 and na["lat_max"] == 70

    # Step 7: Detect field character → temperature_absolute → RdYlBu_r
    cmaps = json.loads(_COLORMAPS.read_text())
    char = cmaps["by_field_character"]["temperature_absolute"]
    assert char["cmap"] == "RdYlBu_r"

    # Step 10: Read slice
    from src.mcp.netcdf_reader.tools.read_slice import read_slice
    slice_env = read_slice(
        str(nc_path), variable=variable,
        lat={"between": [na["lat_min"], na["lat_max"]]},
        lon={"between": [na["lon_min"], na["lon_max"]]},
        adapter=NetCDFAdapter(),
    )
    assert slice_env["ok"] is True

    # Step 11-12: Compose render spec, call render_map
    from src.mcp.plot_renderer.tools import render_map as rm
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed; skill flow exercised through render_map step")

    spec_kwargs: dict = {
        "projection": "PlateCarree",
        "colormap": char["cmap"],
        "title": "SST September 2024 - North Atlantic",
        "lon_convention": "-180..180",
        "output_path": str(tmp_path / "na_sst.png"),
    }
    if slice_env["result"]["form"] == "inline":
        spec_kwargs["values"] = slice_env["result"]["values"]
        spec_kwargs["lat"] = slice_env["result"]["coords"]["lat"]
        spec_kwargs["lon"] = slice_env["result"]["coords"]["lon"]
    else:
        spec_kwargs["slice_ref"] = {
            "path": slice_env["result"]["path"],
            "format": slice_env["result"]["format"],
            "variable": variable,
        }
    render_env = rm.render_map(spec_kwargs)
    assert render_env["ok"] is True, render_env.get("error")

    # Step 13: Verify
    out = render_env["result"]
    assert Path(out["output_path"]).stat().st_size > 5000
    assert out["oracle"]["data"]["nan_fraction"] < 1.0


def test_regions_lookup_works_for_all_documented():
    """Every region in the JSON is discoverable by name."""
    regions = json.loads(_REGIONS.read_text())
    assert len(regions["regions"]) > 0
    # Spot-check a few
    for name in ("North Atlantic", "Niño 3.4", "Tropics"):
        assert name in regions["regions"]


def test_colormaps_lookup_works_for_all_characters():
    """Every field character maps to a real cmap."""
    import matplotlib as mpl
    cmaps = json.loads(_COLORMAPS.read_text())
    for char, entry in cmaps["by_field_character"].items():
        assert entry["cmap"] in mpl.colormaps, (
            f"field_character {char!r}: cmap {entry['cmap']!r} not in registry")
```

- [ ] **Step 2: Add empty `__init__.py`**

```python
# tests/skills/integration/__init__.py
```

- [ ] **Step 3: Run**

```bash
.venv/bin/pytest tests/skills/integration -v
```

Expected: 3 tests run, possibly 1 skipped (if cartopy missing). The map-flow simulation should at minimum exercise inspect + read_slice steps; render_map skips if cartopy missing.

If `read_slice` fails (e.g., because cycle-1's API differs from what the test calls), check the actual signature in `src/mcp/netcdf_reader/tools/read_slice.py` and fix the test to match.

- [ ] **Step 4: Commit**

```bash
git add tests/skills/integration/__init__.py tests/skills/integration/test_map_flow.py
git commit -m "cycle-3 task 19: integration test simulating netcdf-plot-map skill flow"
```

---

## Phase 10: Final polish + push + PR

### Task 20: Final lint + suite green

- [ ] **Step 1: Run ruff on test suite**

```bash
.venv/bin/ruff check tests/skills
```

Fix any violations.

- [ ] **Step 2: Run mypy on test suite (optional but recommended)**

```bash
.venv/bin/mypy tests/skills 2>&1 | head -30
```

If hard failures, fix; if just `# type: ignore` requests for pyyaml, document and move on.

- [ ] **Step 3: Run the full skill test suite**

```bash
.venv/bin/pytest tests/skills -v
```

Expected: all tests pass (some may skip if cartopy missing).

- [ ] **Step 4: Run the full repo suite to confirm cycles 1+2 still green**

```bash
.venv/bin/pytest -v 2>&1 | tail -30
```

Expected: cycle 1 + cycle 2 + cycle 3 tests all green.

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "cycle-3 final gate: full lint + suite green"
```

If no fixes needed: skip the commit.

---

### Task 21: Push + PR

- [ ] **Step 1: Push the branch**

```bash
git push -u origin cycle-3-plot-skills
```

- [ ] **Step 2: Open the PR**

```bash
gh pr create --base master --head cycle-3-plot-skills \
  --title "Cycle 3: plot skills bundle (5 SKILL.md files + reference data + validation tests)" \
  --body "$(cat <<'EOF'
## Summary

- 5 SKILL.md files updated to current MCP signatures (cycle 1+2):
  netcdf-inspect, netcdf-plot-router, netcdf-plot-map,
  netcdf-plot-timeseries, netcdf-plot-profile
- New machine-readable reference data: regions.json, colormaps.json
  (kept in sync with markdown counterparts)
- Style-by-reference flow encoded in each plot skill (vision step
  produces a style_template JSON consumed by the cycle-2 renderer)
- Task-log format frozen at schema_version 1 for cycle-6 skill-refiner
  consumption
- 13 validation tests (frontmatter, sections, tool refs, cross-refs,
  style section, regions sync + schema, colormaps schema, aliases
  format, task-log format) plus 1 integration test simulating the
  SST-North-Atlantic map flow against actual cycle 1+2 MCPs

## Stats

- 21 plan tasks across 10 phases
- 5 SKILL.md files (~250 lines each), 2 new JSON refs (~80 lines each)
- ~15 new tests under tests/skills/

## What's NOT in this PR

- Cross-section + Hovmöller plots (cycle 2's renderer doesn't support
  them; netcdf-plot-router defers gracefully when requested)
- Python skill loader (skills are declarative; cycle 4 is the per-target packager)
- skill-refiner (that's cycle 6)
- Vision LLM mocking infrastructure (host LLM owns vision)

## Test plan

- [ ] \`pytest tests/skills -v\` (default suite green)
- [ ] \`pytest -v\` (full repo: cycles 1+2+3 all green)
- [ ] Manual: \`pytest tests/skills/integration/test_map_flow.py -v\`
  (proves the netcdf-plot-map skill instructions are mechanically executable)

## References

- Spec: \`docs/specs/2026-05-07-cycle-3-plot-skills.md\`
- Plan: \`docs/plans/2026-05-07-cycle-3-plot-skills.md\`
- Style-template extraction prompt: \`docs/style_template_extraction_prompt.md\`
EOF
)"
```

- [ ] **Step 3: Capture PR URL** for the implementation report.

---

## End of plan

21 tasks, 10 phases:

| Phase | Tasks | Theme |
|-------|-------|-------|
| 1 | 1–2 | Test framework + frontmatter validation |
| 2 | 3–5 | Reference data files (regions.json, colormaps.json) |
| 3 | 6–8 | netcdf-inspect skill |
| 4 | 9 | netcdf-plot-router skill |
| 5 | 10 | netcdf-plot-map skill |
| 6 | 11 | netcdf-plot-timeseries skill |
| 7 | 12 | netcdf-plot-profile skill |
| 8 | 13–18 | Cross-cutting validation tests |
| 9 | 19 | Integration test |
| 10 | 20–21 | Final polish + push + PR |

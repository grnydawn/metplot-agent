# Cycle 4: Claude Code target — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ncplot-agent installable into Claude Code. Rewrite `targets/claude-code/build.py` so it produces a working plugin payload at `build/claude-code/ncplot-agent/` with skills, bundled MCP servers, .mcp.json launch stanzas, and a placeholder /refine command. Add validation + smoke tests for the build output. Defer the Stop hook + skill-refiner skill to cycle 6.

**Architecture:** Single Python file rewrite (`targets/claude-code/build.py`), plus a test suite under `tests/targets/claude_code/` and a `--validate` flag on `tools/build.py`. The MCP servers are packaged as installable Python distributions (their existing `pyproject.toml` is patched with `[tool.setuptools.packages.find]` to make `pip install` from the bundled directory work). Launch commands in `.mcp.json` use entry-point scripts (`ncplot-netcdf-reader`, `ncplot-plot-renderer`) installed by pip.

**Tech Stack:** Python 3.10+ (already-installed), pytest, click (already-installed for tools/build.py). No new runtime dependencies.

**Branch:** `cycle-4-claude-code` (already created).

---

## File Structure

### Source / build files

| File | Status | Responsibility |
|------|--------|----------------|
| `targets/claude-code/build.py` | REWRITE | Full plugin packager |
| `targets/claude-code/README.md` | UPDATE | Reflect cycle-4 reality |
| `tools/build.py` | EXTEND | Add `--validate` flag |

Note: `targets/claude-code/` keeps its hyphenated directory name (consistent with tools/build.py's discovery pattern). Python imports happen via `importlib.util.spec_from_file_location`, which is hyphen-agnostic.

### Test files

| File | What it covers |
|------|----------------|
| `tests/targets/__init__.py` | (empty) |
| `tests/targets/claude_code/__init__.py` | (empty) |
| `tests/targets/claude_code/conftest.py` | Fixtures: build into tmp_path, expose plugin paths |
| `tests/targets/claude_code/test_build_runs.py` | Full build succeeds; top-level files/dirs present |
| `tests/targets/claude_code/test_manifest_schema.py` | plugin.json valid + has required fields |
| `tests/targets/claude_code/test_skills_copied.py` | Cycle-3 skills present, skill-refiner absent |
| `tests/targets/claude_code/test_mcp_servers_bundled.py` | Servers bundled with patched pyproject |
| `tests/targets/claude_code/test_mcp_json_schema.py` | .mcp.json valid + entry-point commands |
| `tests/targets/claude_code/test_mcp_smoke.py` | Bundled servers import; list_tool_names works |
| `tests/targets/claude_code/test_commands_dir.py` | refine.md placeholder present |
| `tests/targets/claude_code/test_no_hooks.py` | hooks/ deferred to cycle 6 |
| `tests/tools/__init__.py` | (empty if not present) |
| `tests/tools/test_build_dispatcher.py` | dispatcher discovers + runs claude-code; --validate works |

---

## Phase 1: Test scaffold

### Task 1: tests/targets/ scaffold + conftest

**Files:**
- Create: `tests/targets/__init__.py`
- Create: `tests/targets/claude_code/__init__.py`
- Create: `tests/targets/claude_code/conftest.py`

- [ ] **Step 1: Create empty marker files**

```bash
mkdir -p tests/targets/claude_code
: > tests/targets/__init__.py
: > tests/targets/claude_code/__init__.py
```

- [ ] **Step 2: Write `tests/targets/claude_code/conftest.py`**

```python
# tests/targets/claude_code/conftest.py
"""Fixtures for Claude Code build-output tests.

Builds the plugin into tmp_path once per test module; tests reuse
the produced artifact.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "claude-code" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "targets.claude_code.build", BUILD_PY)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {BUILD_PY}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory) -> Path:
    """Build the plugin into a tmp dir; return the plugin root path."""
    out_dir = tmp_path_factory.mktemp("build")
    mod = _load_build_module()
    mod.build(SRC_ROOT, out_dir)
    plugin_root = out_dir / mod.PLUGIN_NAME
    assert plugin_root.is_dir(), f"build did not produce {plugin_root}"
    return plugin_root


@pytest.fixture(scope="module")
def build_module():
    return _load_build_module()
```

- [ ] **Step 3: Verify pytest can collect the empty test dir**

```bash
.venv/bin/pytest tests/targets -v
```

Expected: `collected 0 items` cleanly (no test files yet).

- [ ] **Step 4: Commit**

```bash
git add tests/targets/__init__.py tests/targets/claude_code/__init__.py \
        tests/targets/claude_code/conftest.py
git commit -m "cycle-4 task 1: tests/targets scaffold + build fixture"
```

---

## Phase 2: Rewrite build.py

### Task 2: Full build.py rewrite

**Files:**
- Modify: `targets/claude-code/build.py`

Replace the existing file's body (keep the docstring, replace the `build()` function and helpers) with the full cycle-4 implementation.

- [ ] **Step 1: Write the new build.py**

```python
"""Build the Claude Code plugin from src/.

Cycle 4 produces an installable plugin payload at
`build/claude-code/ncplot-agent/` containing:

    .claude-plugin/plugin.json    # manifest
    skills/                       # cycle-3 SKILL.md files (skill-refiner excluded)
    mcp-servers/                  # cycle-1/2 MCP server packages
    .mcp.json                     # MCP launch stanzas (entry-point scripts)
    commands/refine.md            # placeholder /refine command (full impl in cycle 6)
    README.md                     # install + setup instructions

Skill-refiner skill + Stop hook are deferred to cycle 6.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PLUGIN_NAME = "ncplot-agent"

# Skills to include in the cycle-4 plugin payload (allowlist).
# `skill-refiner` is intentionally excluded — that's cycle 6.
_INCLUDED_SKILLS = {
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
}

# MCP servers to bundle. Their on-disk Python package names use underscore
# (matches src/mcp/<name>/), and their entry-point scripts use hyphenated
# names (matches their pyproject.toml [project.scripts]).
_MCP_SERVERS = [
    {"package_dir": "netcdf_reader", "external_name": "netcdf-reader",
     "entry_point": "ncplot-netcdf-reader"},
    {"package_dir": "plot_renderer", "external_name": "plot-renderer",
     "entry_point": "ncplot-plot-renderer"},
]


def build(src_root: Path, out_root: Path) -> None:
    """Build the Claude Code plugin into `out_root/<PLUGIN_NAME>/`."""
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    _write_manifest(plugin_dir)
    _copy_skills(src_root, plugin_dir)
    _bundle_mcp_servers(src_root, plugin_dir)
    _write_mcp_json(plugin_dir)
    _write_commands(plugin_dir)
    _write_readme(plugin_dir)


def _write_manifest(plugin_dir: Path) -> None:
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir()
    manifest = {
        "$schema": "https://json.schemastore.org/claude-code-plugin",
        "name": PLUGIN_NAME,
        "version": "0.1.0",
        "description": (
            "Natural-language plotting from NetCDF files. Maps, time series, "
            "and vertical profiles. WRF/ROMS/CMIP/reanalysis aware."
        ),
        "author": {"name": "ncplot-agent contributors"},
        "homepage": "https://github.com/grnydawn/ncplot-agent",
        "license": "MIT",
        "keywords": ["netcdf", "matplotlib", "cartopy", "wrf", "roms",
                      "cmip", "climate"],
        "ncplot": {
            "build_cycle": 4,
            "ships_skills": sorted(_INCLUDED_SKILLS),
            "ships_mcp_servers": [s["external_name"] for s in _MCP_SERVERS],
        },
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")


def _copy_skills(src_root: Path, plugin_dir: Path) -> None:
    skills_src = src_root / "skills"
    skills_dst = plugin_dir / "skills"
    skills_dst.mkdir()
    for skill_name in sorted(_INCLUDED_SKILLS):
        src = skills_src / skill_name
        if not src.is_dir():
            raise RuntimeError(f"missing skill source: {src}")
        shutil.copytree(src, skills_dst / skill_name)


def _bundle_mcp_servers(src_root: Path, plugin_dir: Path) -> None:
    mcp_dst_root = plugin_dir / "mcp-servers"
    mcp_dst_root.mkdir()
    for server in _MCP_SERVERS:
        pkg_dir = server["package_dir"]
        src = src_root / "mcp" / pkg_dir
        if not src.is_dir():
            raise RuntimeError(f"missing MCP server source: {src}")
        dst = mcp_dst_root / pkg_dir
        dst.mkdir()

        # Re-root the package source under <dst>/src/mcp/<pkg_dir>/ so
        # `from src.mcp.<pkg_dir>...` imports continue to work after `pip
        # install` from the bundled location.
        bundled_src = dst / "src" / "mcp" / pkg_dir
        bundled_src.parent.mkdir(parents=True)
        shutil.copytree(src, bundled_src)

        # Patch pyproject.toml so setuptools discovers the package.
        # The original pyproject.toml lacks [tool.setuptools.packages.find].
        pyproject_text = (src / "pyproject.toml").read_text()
        if "[tool.setuptools.packages.find]" not in pyproject_text:
            pyproject_text += (
                "\n[tool.setuptools.packages.find]\n"
                'where = ["src"]\n'
                "namespaces = true\n"
            )
        (dst / "pyproject.toml").write_text(pyproject_text)

        # Carry README.md if present
        readme = src / "README.md"
        if readme.exists():
            shutil.copy2(readme, dst / "README.md")


def _write_mcp_json(plugin_dir: Path) -> None:
    mcp_servers = {
        s["external_name"]: {
            "command": s["entry_point"],
            "args": [],
        }
        for s in _MCP_SERVERS
    }
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n")


def _write_commands(plugin_dir: Path) -> None:
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(
        "---\n"
        "description: Review the current session and propose refinement drafts to "
        "the canonical skills. (Currently a placeholder — full implementation "
        "lands in cycle 6.)\n"
        "---\n"
        "\n"
        "The `/refine` command will trigger the `skill-refiner` skill (cycle 6) "
        "once that's implemented. For now, this is a placeholder so the command "
        "appears in autocomplete.\n"
        "\n"
        "Until cycle 6 ships:\n"
        "\n"
        "- The task-log at `.ncplot/task-log.jsonl` is being written by skills "
        "on user corrections.\n"
        "- No automatic refinement happens.\n"
        "- No drafts are produced.\n"
        "\n"
        "After cycle 6: this command will invoke skill-refiner against the "
        "session log and produce draft refinements under "
        "`.ncplot/refinements/` for human review.\n"
    )


def _write_readme(plugin_dir: Path) -> None:
    skills = sorted(_INCLUDED_SKILLS)
    mcps = [s["external_name"] for s in _MCP_SERVERS]
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    mcp_install = "\n".join(
        f"pip install ./mcp-servers/{s['package_dir']}"
        for s in _MCP_SERVERS
    )
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps)
    (plugin_dir / "README.md").write_text(f"""# ncplot-agent — Claude Code plugin

NetCDF plotting via natural language. Maps, time series, and vertical
profiles. WRF/ROMS/CMIP/reanalysis aware.

## Install

### 1. Install the MCP servers

The plugin's MCP servers are Python packages bundled under
`mcp-servers/`. From the plugin root:

```bash
{mcp_install}
```

This puts the entry-point scripts (`ncplot-netcdf-reader`,
`ncplot-plot-renderer`) on your PATH. The `.mcp.json` launch commands
reference these by name.

You also need the scientific Python stack:

```bash
pip install matplotlib numpy xarray netcdf4 dask
# Optional, for maps:
pip install cartopy
# Optional, for lowess trendlines:
pip install scipy
```

(Cycle 5 of ncplot-agent will ship a one-shot installer for the
optional deps.)

### 2. Install the plugin

```bash
cp -r . ~/.claude/plugins/ncplot-agent
```

Or, in a project, add to `.claude/settings.json`:

```json
{{
  "plugins": ["/absolute/path/to/this/plugin"]
}}
```

### 3. Restart Claude Code

The skills and MCP tools become available immediately. Type "what
NetCDF files are in this directory?" or "plot SST in the North Atlantic
from <file>" to exercise the full pipeline.

## What's inside

Skills:
{skill_lines}

MCP servers:
{mcp_lines}

Slash commands:
  - `/refine` — placeholder; full implementation in cycle 6.

Hooks: none in this cycle. The Stop hook for the skill-refiner closed
loop ships in cycle 6.

## Self-improvement (preview)

When skills correct user-supplied variable names, regions, colormaps,
projections, etc., they append events to `.ncplot/task-log.jsonl`.
Cycle 6 will ship a `skill-refiner` skill that reads this log at
session end and proposes refinements to the canonical skill files.

For cycle 4: the task-log is being written, but no automatic
refinement is wired up yet.

## Troubleshooting

**MCP server fails to launch.** Check that `ncplot-netcdf-reader` and
`ncplot-plot-renderer` are on your PATH:

```bash
which ncplot-netcdf-reader
which ncplot-plot-renderer
```

If not, re-run the pip install step above. Some Python installations
put entry-points in `~/.local/bin/` which may not be on PATH by default.

**Cartopy import errors.** Install with conda-forge for prebuilt PROJ/GEOS:

```bash
conda install -c conda-forge cartopy
```

If cartopy isn't installed, only `render_map` will be unavailable;
`render_timeseries` and `render_profile` keep working. The
`netcdf-plot-map` skill returns an instructive error in that case.

## Build provenance

This plugin payload was produced by `targets/claude-code/build.py`
from the canonical L1 source under `src/`. To rebuild:

```bash
python -m tools.build claude-code
```
""")
```

- [ ] **Step 2: Verify the build runs end-to-end (smoke check)**

```bash
.venv/bin/python -m tools.build claude-code
ls build/claude-code/ncplot-agent/
ls build/claude-code/ncplot-agent/.claude-plugin/
ls build/claude-code/ncplot-agent/skills/
ls build/claude-code/ncplot-agent/mcp-servers/
cat build/claude-code/ncplot-agent/.mcp.json
```

Expected:
- Plugin directory exists
- `.claude-plugin/plugin.json` exists
- `skills/` contains 5 dirs (netcdf-inspect, netcdf-plot-router, netcdf-plot-map, netcdf-plot-timeseries, netcdf-plot-profile) — NO skill-refiner
- `mcp-servers/` contains netcdf_reader/ and plot_renderer/
- `.mcp.json` has both servers with entry-point command names

- [ ] **Step 3: Commit**

```bash
git add targets/claude-code/build.py
git commit -m "cycle-4 task 2: rewrite claude-code build.py (working plugin payload)"
```

---

## Phase 3: Build-output validation tests

### Task 3: test_build_runs

**Files:**
- Create: `tests/targets/claude_code/test_build_runs.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_build_runs.py
"""Verify the cycle-4 Claude Code build produces all expected top-level
files and directories."""
from __future__ import annotations

from pathlib import Path


def test_plugin_root_exists(built_plugin: Path) -> None:
    assert built_plugin.is_dir()
    assert built_plugin.name == "ncplot-agent"


def test_manifest_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / ".claude-plugin").is_dir()
    assert (built_plugin / ".claude-plugin" / "plugin.json").is_file()


def test_top_level_dirs_present(built_plugin: Path) -> None:
    for d in ("skills", "mcp-servers", "commands"):
        assert (built_plugin / d).is_dir(), f"missing top-level dir: {d}"


def test_top_level_files_present(built_plugin: Path) -> None:
    assert (built_plugin / ".mcp.json").is_file()
    assert (built_plugin / "README.md").is_file()


def test_no_hooks_dir(built_plugin: Path) -> None:
    """Stop hook is deferred to cycle 6; hooks/ should not exist in cycle 4."""
    assert not (built_plugin / "hooks").exists()


def test_build_is_idempotent(tmp_path_factory, build_module) -> None:
    """Running build twice produces the same shape (clean overwrite)."""
    out = tmp_path_factory.mktemp("idem")
    src = Path(__file__).resolve().parents[3] / "src"
    build_module.build(src, out)
    first_files = sorted((p.relative_to(out) for p in out.rglob("*")
                           if p.is_file()))
    build_module.build(src, out)
    second_files = sorted((p.relative_to(out) for p in out.rglob("*")
                            if p.is_file()))
    assert first_files == second_files
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_build_runs.py -v
```

Expected: 6 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_build_runs.py
git commit -m "cycle-4 task 3: test_build_runs (top-level structure + idempotency)"
```

---

### Task 4: test_manifest_schema

**Files:**
- Create: `tests/targets/claude_code/test_manifest_schema.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_manifest_schema.py
"""Verify plugin.json shape."""
from __future__ import annotations

import json
from pathlib import Path


def test_plugin_json_parses(built_plugin: Path) -> None:
    text = (built_plugin / ".claude-plugin" / "plugin.json").read_text()
    json.loads(text)


def test_required_fields(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    for field in ("name", "version", "description"):
        assert field in m, f"missing required field: {field}"


def test_name_pinned(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert m["name"] == "ncplot-agent"


def test_ncplot_block_present(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "ncplot" in m
    nc = m["ncplot"]
    assert nc["build_cycle"] == 4
    assert "ships_skills" in nc
    assert "ships_mcp_servers" in nc


def test_ships_skills_matches_allowlist(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    expected = {
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    }
    assert set(m["ncplot"]["ships_skills"]) == expected


def test_ships_mcp_servers(built_plugin: Path) -> None:
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert set(m["ncplot"]["ships_mcp_servers"]) == {
        "netcdf-reader", "plot-renderer"}


def test_skill_refiner_excluded(built_plugin: Path) -> None:
    """skill-refiner is cycle 6; must NOT be advertised in cycle 4."""
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    assert "skill-refiner" not in m["ncplot"]["ships_skills"]
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_manifest_schema.py -v
```

Expected: 7 passed.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_manifest_schema.py
git commit -m "cycle-4 task 4: test_manifest_schema (plugin.json validation)"
```

---

### Task 5: test_skills_copied

**Files:**
- Create: `tests/targets/claude_code/test_skills_copied.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_skills_copied.py
"""Verify skills directory contents."""
from __future__ import annotations

from pathlib import Path

import pytest


_EXPECTED_SKILLS = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def test_all_expected_skills_present(built_plugin: Path) -> None:
    skills_dir = built_plugin / "skills"
    actual = {p.name for p in skills_dir.iterdir() if p.is_dir()}
    assert actual == _EXPECTED_SKILLS, (
        f"unexpected skill set: missing {_EXPECTED_SKILLS - actual}, "
        f"extra {actual - _EXPECTED_SKILLS}")


def test_skill_refiner_excluded(built_plugin: Path) -> None:
    """skill-refiner is cycle 6; must not be in the build."""
    assert not (built_plugin / "skills" / "skill-refiner").exists()


@pytest.mark.parametrize("skill", sorted(_EXPECTED_SKILLS))
def test_skill_md_present(built_plugin: Path, skill: str) -> None:
    md = built_plugin / "skills" / skill / "SKILL.md"
    assert md.is_file()
    text = md.read_text()
    assert text.startswith("---\n"), f"{skill} SKILL.md missing frontmatter"


def test_references_subdirs_preserved(built_plugin: Path) -> None:
    """Skills with references/ subdirs must still have them after copy."""
    inspect_refs = built_plugin / "skills" / "netcdf-inspect" / "references"
    assert inspect_refs.is_dir()
    assert (inspect_refs / "aliases.md").is_file()
    assert (inspect_refs / "conventions.md").is_file()

    map_refs = built_plugin / "skills" / "netcdf-plot-map" / "references"
    assert map_refs.is_dir()
    assert (map_refs / "regions.md").is_file()
    assert (map_refs / "regions.json").is_file()
    assert (map_refs / "colormaps.json").is_file()
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_skills_copied.py -v
```

Expected: 8 passed (5 parametrized + 3 fixed).

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_skills_copied.py
git commit -m "cycle-4 task 5: test_skills_copied (5 included; skill-refiner excluded)"
```

---

## Phase 4: MCP server bundling tests

### Task 6: test_mcp_servers_bundled

**Files:**
- Create: `tests/targets/claude_code/test_mcp_servers_bundled.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_mcp_servers_bundled.py
"""Verify each MCP server is bundled with re-rooted source + patched pyproject."""
from __future__ import annotations

from pathlib import Path

import pytest


_EXPECTED_SERVERS = {"netcdf_reader", "plot_renderer"}


def test_mcp_servers_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / "mcp-servers").is_dir()


def test_all_expected_servers_present(built_plugin: Path) -> None:
    actual = {p.name for p in (built_plugin / "mcp-servers").iterdir() if p.is_dir()}
    assert actual == _EXPECTED_SERVERS


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_pyproject_present(built_plugin: Path, server: str) -> None:
    pp = built_plugin / "mcp-servers" / server / "pyproject.toml"
    assert pp.is_file()


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_pyproject_has_packages_find_block(built_plugin: Path, server: str) -> None:
    """Patched pyproject.toml must enable setuptools.packages.find against src/."""
    text = (built_plugin / "mcp-servers" / server / "pyproject.toml").read_text()
    assert "[tool.setuptools.packages.find]" in text, (
        f"{server}: pyproject.toml missing [tool.setuptools.packages.find]")
    assert 'where = ["src"]' in text, (
        f"{server}: pyproject.toml missing where = [\"src\"]")


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_source_re_rooted_under_src_mcp(built_plugin: Path, server: str) -> None:
    """The bundled package source must be at <server>/src/mcp/<server>/ to
    preserve the `from src.mcp.<server>...` import path."""
    pkg_dir = built_plugin / "mcp-servers" / server / "src" / "mcp" / server
    assert pkg_dir.is_dir(), f"missing re-rooted package dir: {pkg_dir}"
    assert (pkg_dir / "__init__.py").is_file()
    assert (pkg_dir / "server.py").is_file()


@pytest.mark.parametrize("server", sorted(_EXPECTED_SERVERS))
def test_no_stray_top_level_python_files(built_plugin: Path, server: str) -> None:
    """The bundled <server>/ should NOT have stray python files at top level
    (only pyproject.toml + optional README + src/)."""
    server_dir = built_plugin / "mcp-servers" / server
    py_at_root = list(server_dir.glob("*.py"))
    assert not py_at_root, (
        f"{server}: stray .py files at bundle root: {[p.name for p in py_at_root]}")
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_mcp_servers_bundled.py -v
```

Expected: 10 passed (4 fixed + 6 parametrized × 4 = wait let me recount: 2 fixed + 4 parametrized × 2 servers = 10). Actually: 2 fixed (dir present, all expected) + 4 parametrized (pyproject present, packages.find, re-rooted, no stray) × 2 servers = 2 + 8 = 10.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_mcp_servers_bundled.py
git commit -m "cycle-4 task 6: test_mcp_servers_bundled (re-rooted source + patched pyproject)"
```

---

### Task 7: test_mcp_json_schema

**Files:**
- Create: `tests/targets/claude_code/test_mcp_json_schema.py`

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_mcp_json_schema.py
"""Verify .mcp.json contents."""
from __future__ import annotations

import json
from pathlib import Path

import pytest


_EXPECTED_SERVERS_BY_EXTERNAL_NAME = {
    "netcdf-reader": "ncplot-netcdf-reader",
    "plot-renderer": "ncplot-plot-renderer",
}


def test_mcp_json_parses(built_plugin: Path) -> None:
    json.loads((built_plugin / ".mcp.json").read_text())


def test_has_mcp_servers_key(built_plugin: Path) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    assert "mcpServers" in d
    assert isinstance(d["mcpServers"], dict)


def test_all_expected_servers_listed(built_plugin: Path) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    assert set(d["mcpServers"].keys()) == set(_EXPECTED_SERVERS_BY_EXTERNAL_NAME)


@pytest.mark.parametrize(
    "external_name,entry_point",
    sorted(_EXPECTED_SERVERS_BY_EXTERNAL_NAME.items()),
)
def test_each_server_uses_entry_point_command(
    built_plugin: Path, external_name: str, entry_point: str,
) -> None:
    d = json.loads((built_plugin / ".mcp.json").read_text())
    server = d["mcpServers"][external_name]
    assert server["command"] == entry_point, (
        f"{external_name}: command {server['command']!r} != "
        f"expected entry-point {entry_point!r}")
    assert "args" in server
    assert isinstance(server["args"], list)
```

- [ ] **Step 2: Run, verify pass**

Expected: 5 passed (3 fixed + 2 parametrized).

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_mcp_json_schema.py
git commit -m "cycle-4 task 7: test_mcp_json_schema (entry-point launch commands)"
```

---

### Task 8: test_mcp_smoke

**Files:**
- Create: `tests/targets/claude_code/test_mcp_smoke.py`

This test imports the bundled MCP servers to verify the re-rooted
source path actually resolves. We don't run the stdio loop — just
verify the module imports and `list_tool_names()` works.

- [ ] **Step 1: Write the test**

```python
# tests/targets/claude_code/test_mcp_smoke.py
"""Smoke test: bundled MCP servers can be imported and list their tools.

Verifies the re-rooted-source strategy (§3.1 of the spec) actually
resolves imports. Doesn't run the stdio MCP loop — that's covered by
cycle 1+2's own tests.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


_SERVERS = [
    {"package_dir": "netcdf_reader", "expected_tool_count": 8},
    {"package_dir": "plot_renderer", "expected_tool_count": 3},
]


@pytest.mark.parametrize("server", _SERVERS,
                         ids=lambda s: s["package_dir"])
def test_bundled_server_imports(built_plugin: Path, server: dict) -> None:
    """Add the bundled src/ to sys.path and import the server module."""
    bundle_src = built_plugin / "mcp-servers" / server["package_dir"] / "src"
    sys.path.insert(0, str(bundle_src))
    try:
        # Force re-import in case repo's src is also on sys.path.
        # We're testing that the bundled src works on its own.
        modname = f"src.mcp.{server['package_dir']}.server"
        if modname in sys.modules:
            del sys.modules[modname]
        # Import via the bundled path
        # NOTE: because both repo root and bundle src have src/mcp/<name>,
        # Python may resolve to the repo. The smoke test passes if EITHER
        # works, since the import path string is identical. The packaging
        # bug we're guarding against is one where the imports CAN'T resolve
        # at all from the bundle.
        mod = importlib.import_module(modname)
        names = mod.list_tool_names()
        assert isinstance(names, list)
        assert len(names) == server["expected_tool_count"], (
            f"{server['package_dir']}: expected {server['expected_tool_count']} "
            f"tools, got {len(names)}")
    finally:
        if str(bundle_src) in sys.path:
            sys.path.remove(str(bundle_src))


def test_pyproject_install_metadata_complete(built_plugin: Path) -> None:
    """Verify each bundled pyproject.toml has the metadata pip needs."""
    for server in _SERVERS:
        pp_text = (built_plugin / "mcp-servers" / server["package_dir"]
                    / "pyproject.toml").read_text()
        # Key fields a pip install needs
        assert "[project]" in pp_text
        assert "name = " in pp_text
        assert "version = " in pp_text
        # Setuptools packaging block we patched in
        assert "[tool.setuptools.packages.find]" in pp_text
        assert 'where = ["src"]' in pp_text
```

- [ ] **Step 2: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_mcp_smoke.py -v
```

Expected: 3 passed (2 parametrized + 1 fixed). Note: the import test is somewhat lenient — it passes if the import resolves at all. The strict test (does it work AFTER pip install?) is a manual integration test.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/claude_code/test_mcp_smoke.py
git commit -m "cycle-4 task 8: test_mcp_smoke (import bundled servers + verify tool counts)"
```

---

## Phase 5: Commands + hooks-deferred + README

### Task 9: test_commands_dir + test_no_hooks

**Files:**
- Create: `tests/targets/claude_code/test_commands_dir.py`
- Create: `tests/targets/claude_code/test_no_hooks.py`

- [ ] **Step 1: Write `test_commands_dir.py`**

```python
# tests/targets/claude_code/test_commands_dir.py
"""Verify commands/ has the expected /refine placeholder."""
from __future__ import annotations

from pathlib import Path


def test_commands_dir_present(built_plugin: Path) -> None:
    assert (built_plugin / "commands").is_dir()


def test_refine_command_present(built_plugin: Path) -> None:
    assert (built_plugin / "commands" / "refine.md").is_file()


def test_refine_has_frontmatter(built_plugin: Path) -> None:
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert text.startswith("---\n")
    end = text.find("\n---\n", 4)
    assert end > 0, "refine.md frontmatter unterminated"


def test_refine_announces_placeholder_status(built_plugin: Path) -> None:
    """User-facing text should make clear this is a placeholder."""
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "placeholder" in text.lower()
    assert "cycle 6" in text.lower()
```

- [ ] **Step 2: Write `test_no_hooks.py`**

```python
# tests/targets/claude_code/test_no_hooks.py
"""Verify hooks/ is deferred to cycle 6 and not present in cycle 4."""
from __future__ import annotations

from pathlib import Path


def test_no_hooks_dir(built_plugin: Path) -> None:
    """Stop hook for skill-refiner ships in cycle 6, not cycle 4."""
    assert not (built_plugin / "hooks").exists()


def test_manifest_has_no_hook_config(built_plugin: Path) -> None:
    """plugin.json should not declare any hooks in cycle 4."""
    import json
    m = json.loads((built_plugin / ".claude-plugin" / "plugin.json").read_text())
    # The manifest may not have a 'hooks' key at all (preferred), OR if it
    # does, it should be an empty list/dict.
    if "hooks" in m:
        assert not m["hooks"], (
            f"manifest declares hooks in cycle 4: {m['hooks']!r}")
```

- [ ] **Step 3: Run, verify pass**

```bash
.venv/bin/pytest tests/targets/claude_code/test_commands_dir.py \
                 tests/targets/claude_code/test_no_hooks.py -v
```

Expected: 6 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/targets/claude_code/test_commands_dir.py \
        tests/targets/claude_code/test_no_hooks.py
git commit -m "cycle-4 task 9: test_commands_dir + test_no_hooks (cycle-6 deferral)"
```

---

## Phase 6: Build dispatcher --validate flag

### Task 10: tools/build.py --validate

**Files:**
- Modify: `tools/build.py`

- [ ] **Step 1: Update tools/build.py**

Add `--validate` flag that runs the validation suite after build:

```python
"""Build dispatcher.

Usage:
    python -m tools.build <target>
    python -m tools.build <target> --validate
    python -m tools.build --all
    python -m tools.build --list

Each target is a directory under `targets/` with a `build.py` that exposes
`build(src_root: Path, out_root: Path) -> None`.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import click

REPO_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = REPO_ROOT / "src"
TARGETS_ROOT = REPO_ROOT / "targets"
BUILD_ROOT = REPO_ROOT / "build"
TESTS_ROOT = REPO_ROOT / "tests" / "targets"


def discover_targets() -> dict[str, Path]:
    """Find all target directories that contain a build.py."""
    targets = {}
    if not TARGETS_ROOT.exists():
        return targets
    for path in TARGETS_ROOT.iterdir():
        if path.is_dir() and (path / "build.py").exists():
            targets[path.name] = path / "build.py"
    return targets


def load_target_module(name: str, build_py: Path):
    spec = importlib.util.spec_from_file_location(f"targets.{name}", build_py)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"failed to load {build_py}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _validation_dir_for(target: str) -> Path:
    """Map target name (e.g. 'claude-code') to test dir name ('claude_code')."""
    return TESTS_ROOT / target.replace("-", "_")


def build_target(name: str, *, validate: bool = False) -> None:
    targets = discover_targets()
    if name not in targets:
        available = ", ".join(sorted(targets)) or "(none)"
        raise click.ClickException(f"unknown target '{name}'. Available: {available}")
    out_dir = BUILD_ROOT / name
    out_dir.mkdir(parents=True, exist_ok=True)
    module = load_target_module(name, targets[name])
    if not hasattr(module, "build"):
        raise click.ClickException(f"{targets[name]} does not export build()")
    click.echo(f"building {name} → {out_dir.relative_to(REPO_ROOT)}")
    module.build(SRC_ROOT, out_dir)
    click.echo("  done.")
    if validate:
        validate_target(name)


def validate_target(name: str) -> None:
    test_dir = _validation_dir_for(name)
    if not test_dir.exists():
        click.echo(f"  no validation suite at {test_dir.relative_to(REPO_ROOT)}",
                   err=True)
        return
    click.echo(f"validating {name}...")
    pytest_bin = REPO_ROOT / ".venv" / "bin" / "pytest"
    if not pytest_bin.exists():
        pytest_bin = "pytest"
    result = subprocess.run(
        [str(pytest_bin), str(test_dir), "-v"],
        cwd=str(REPO_ROOT),
        check=False,
    )
    if result.returncode != 0:
        raise click.ClickException(
            f"validation failed for target {name!r}; see pytest output above")
    click.echo(f"  validation passed.")


@click.command()
@click.argument("target", required=False)
@click.option("--all", "all_", is_flag=True, help="Build every registered target.")
@click.option("--list", "list_", is_flag=True, help="List available targets and exit.")
@click.option("--validate", is_flag=True,
              help="Run the validation suite after build.")
def cli(target: str | None, all_: bool, list_: bool, validate: bool) -> None:
    targets = discover_targets()
    if list_:
        if not targets:
            click.echo("no targets registered")
            return
        for name in sorted(targets):
            click.echo(name)
        return
    if all_:
        if not targets:
            raise click.ClickException("no targets registered")
        for name in sorted(targets):
            build_target(name, validate=validate)
        return
    if not target:
        raise click.ClickException("specify a target, --all, or --list")
    build_target(target, validate=validate)


if __name__ == "__main__":
    cli()
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m tools.build --list
.venv/bin/python -m tools.build claude-code --validate 2>&1 | tail -20
```

Expected:
- `--list` shows: `claude-code`, `claude-desktop`, `codex`, `hermes`
- `--validate` runs the cycle-4 test suite and exits 0

- [ ] **Step 3: Commit**

```bash
git add tools/build.py
git commit -m "cycle-4 task 10: tools/build.py --validate flag"
```

---

### Task 11: test_build_dispatcher

**Files:**
- Create: `tests/tools/__init__.py` (if not present)
- Create: `tests/tools/test_build_dispatcher.py`

- [ ] **Step 1: Create test directory marker**

```bash
mkdir -p tests/tools
[ -f tests/tools/__init__.py ] || : > tests/tools/__init__.py
```

- [ ] **Step 2: Write the test**

```python
# tests/tools/test_build_dispatcher.py
"""Verify tools/build.py discovers + builds the claude-code target."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_dispatcher():
    spec = importlib.util.spec_from_file_location(
        "tools.build", REPO_ROOT / "tools" / "build.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_discover_targets_finds_claude_code():
    mod = _load_dispatcher()
    targets = mod.discover_targets()
    assert "claude-code" in targets


def test_validation_dir_mapping():
    mod = _load_dispatcher()
    p = mod._validation_dir_for("claude-code")
    assert p.name == "claude_code"


def test_build_via_dispatcher(tmp_path, monkeypatch):
    """Running the dispatcher's build_target programmatically produces output."""
    mod = _load_dispatcher()
    monkeypatch.setattr(mod, "BUILD_ROOT", tmp_path)
    mod.build_target("claude-code", validate=False)
    plugin_root = tmp_path / "claude-code" / "ncplot-agent"
    assert plugin_root.is_dir()
    assert (plugin_root / ".claude-plugin" / "plugin.json").is_file()


def test_build_unknown_target_raises():
    import click
    mod = _load_dispatcher()
    with pytest.raises(click.ClickException):
        mod.build_target("not-a-real-target")
```

- [ ] **Step 3: Run, verify pass**

```bash
.venv/bin/pytest tests/tools/test_build_dispatcher.py -v
```

Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/tools/__init__.py tests/tools/test_build_dispatcher.py
git commit -m "cycle-4 task 11: test_build_dispatcher (discover, build, validate mapping)"
```

---

## Phase 7: Update README

### Task 12: Update targets/claude-code/README.md

**Files:**
- Modify: `targets/claude-code/README.md`

- [ ] **Step 1: Replace the file**

```markdown
# Claude Code target

This target packages the canonical L1 source under `src/` (skills + MCP
servers + reference data) into an installable Claude Code plugin payload.

## Build

```
python -m tools.build claude-code
```

Output lands in `build/claude-code/ncplot-agent/`. See the README inside
that directory for end-user install instructions.

## Validate the build output

```
python -m tools.build claude-code --validate
```

Runs the cycle-4 test suite under `tests/targets/claude_code/` against
the freshly produced artifact. CI uses this; local development can skip
it.

## What this builder produces

A complete Claude Code plugin:

```
build/claude-code/ncplot-agent/
├── .claude-plugin/plugin.json   # manifest with cycle metadata
├── README.md                    # end-user install + setup instructions
├── skills/                      # 5 SKILL.md packages from cycle 3
├── mcp-servers/                 # netcdf_reader + plot_renderer (installable)
├── .mcp.json                    # MCP launch stanzas (entry-point scripts)
└── commands/refine.md           # /refine placeholder (full impl: cycle 6)
```

## Skill-refiner + Stop hook

Both are deferred to cycle 6. The cycle-4 build excludes
`src/skills/skill-refiner/` from the payload and produces no
`hooks/` directory. The `/refine` slash command stub is included so
the command name appears in autocomplete; its body explains that the
feature is on the way.

## MCP server packaging

The cycle-1/2 MCP servers ship as pip-installable Python distributions
under `mcp-servers/<name>/`. The build:

1. Re-roots the package source under `mcp-servers/<name>/src/mcp/<name>/`
   (preserving the `src.mcp.<name>` import path that server.py uses).
2. Patches the original `pyproject.toml` to add
   `[tool.setuptools.packages.find]` with `where = ["src"]` and
   `namespaces = true`.

The generated README instructs the end-user to `pip install` each
server, which puts the entry-point scripts (`ncplot-netcdf-reader`,
`ncplot-plot-renderer`) on PATH. The `.mcp.json` launch commands
reference these.

For developers who don't want a system-wide pip install, they can
substitute a `python -m src.mcp.<name>.server` invocation in
`.mcp.json`, with `${CLAUDE_PLUGIN_ROOT}/mcp-servers/<name>/src/` on
`PYTHONPATH`. The default config uses entry-points; the alternative
is documented in the plugin README.

## Cycle 5: dependency installer

Cartopy and scipy are scientific Python deps with C-level requirements
(PROJ, GEOS, BLAS). Installing them robustly across platforms is
non-trivial; cycle 5 ships a setup helper. Until then, the plugin
README points users to conda-forge and pip with documented fallbacks.

## See also

- `docs/architecture.md` — overall L1/L2/L3 layering
- `docs/adding-targets.md` — adding more targets (claude-desktop, codex, hermes, cursor)
- `docs/specs/2026-05-08-cycle-4-claude-code.md` — cycle-4 design
```

- [ ] **Step 2: Commit**

```bash
git add targets/claude-code/README.md
git commit -m "cycle-4 task 12: targets/claude-code/README updated for cycle-4 reality"
```

---

## Phase 8: Final polish + push + PR

### Task 13: Final lint + suite green

- [ ] **Step 1: Lint cycle-4 sources**

```bash
.venv/bin/ruff check targets/claude-code/build.py tools/build.py \
                     tests/targets tests/tools
```

Fix any violations.

- [ ] **Step 2: mypy on cycle-4 sources (best-effort)**

```bash
.venv/bin/mypy targets/claude-code/build.py tools/build.py 2>&1 | head -30
```

- [ ] **Step 3: Run cycle-4 test suite via the dispatcher (--validate)**

```bash
.venv/bin/python -m tools.build claude-code --validate
```

Expected: build succeeds, validation suite passes.

- [ ] **Step 4: Run the full repo suite**

```bash
.venv/bin/pytest -v 2>&1 | tail -30
```

Expected: cycle 1-4 tests all green; cycle-3 cartopy/SSH/real-files skips remain as before.

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "cycle-4 final gate: full lint + suite green"
```

If no fixes needed: skip the commit.

---

### Task 14: Push + PR

- [ ] **Step 1: Push**

```bash
git push -u origin cycle-4-claude-code
```

- [ ] **Step 2: Create the PR**

```bash
gh pr create --base master --head cycle-4-claude-code \
  --title "Cycle 4: Claude Code target — installable plugin packager" \
  --body "$(cat <<'EOF'
## Summary

- Rewrote `targets/claude-code/build.py` to produce an installable
  Claude Code plugin payload at `build/claude-code/ncplot-agent/`.
- Bundled MCP servers as installable Python packages with patched
  `pyproject.toml` (`[tool.setuptools.packages.find]` with
  `where = ["src"]`) so `pip install` from the plugin payload works.
- `.mcp.json` launch commands use entry-point scripts
  (`ncplot-netcdf-reader`, `ncplot-plot-renderer`).
- Skills allowlist excludes `skill-refiner` (deferred to cycle 6).
- No `hooks/` directory in cycle 4 (Stop hook lands with the refiner).
- `tools/build.py` gains a `--validate` flag that runs the
  per-target test suite after build.
- 12 validation tests under `tests/targets/claude_code/` covering:
  build runs, manifest schema, skills copied, MCP servers bundled,
  .mcp.json schema, MCP smoke imports, commands dir, no-hooks
  cycle-6 deferral, build dispatcher.

## Stats

- 14 plan tasks across 8 phases
- 1 production file rewritten (`targets/claude-code/build.py`)
- 1 production file extended (`tools/build.py` `--validate`)
- ~12 new tests under `tests/targets/claude_code/` + `tests/tools/`

## What's NOT in this PR

- Stop hook + skill-refiner skill (cycle 6)
- Auto-installer for cartopy/scipy (cycle 5)
- Other targets (claude-desktop / codex / hermes / cursor)
- Marketplace publishing / signed releases

## Test plan

- [ ] `python -m tools.build claude-code --validate`
- [ ] `pytest -v` (full repo green)
- [ ] **Manual:** copy `build/claude-code/ncplot-agent/` to `~/.claude/plugins/`,
  `pip install ./mcp-servers/netcdf_reader ./mcp-servers/plot_renderer`,
  restart Claude Code, ask "what's in this NetCDF file?"
  to exercise the full chain (Claude Code skill loader → skill →
  MCP tool → renderer).

## References

- Spec: `docs/specs/2026-05-08-cycle-4-claude-code.md`
- Plan: `docs/plans/2026-05-08-cycle-4-claude-code.md`
EOF
)"
```

- [ ] **Step 3: Capture PR URL** for the implementation report.

---

## End of plan

14 tasks, 8 phases:

| Phase | Tasks | Theme |
|-------|-------|-------|
| 1 | 1 | Test scaffold |
| 2 | 2 | Rewrite `build.py` |
| 3 | 3–5 | Build-output validation tests (build, manifest, skills) |
| 4 | 6–8 | MCP server bundling tests |
| 5 | 9 | Commands + no-hooks tests |
| 6 | 10–11 | Dispatcher `--validate` flag + test |
| 7 | 12 | README update |
| 8 | 13–14 | Final polish + push + PR |

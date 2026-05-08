# Cycle 7: Multi-host target expansion — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add 5 new build targets (Codex CLI/Desktop, Gemini CLI, Cursor, GitHub Copilot, Antigravity) + polish Claude Desktop, by extracting shared cycle-4 logic into `targets/_common/` and writing thin per-target glue.

**Architecture:** `targets/_common/` houses skills allowlist, MCP server bundling, and shared metadata constants. Each per-target `build.py` is ~50–100 LOC of host-specific manifest emission + MCP launch config + slash-command file (where supported) + README. Hooks + skill-refiner stay deferred to cycle 6.

**Tech Stack:** Python 3.10+, pytest, `tomli_w` (for Codex `config.toml` writing). Will install `tomli_w` if not already in venv.

**Branch:** `cycle-7-multi-host-targets` (already created; research + architecture docs already committed at `133a9a3`, spec at `5070a49`).

---

## File Structure

### New / refactored source files

| File | Status | LOC est. |
|------|--------|----------|
| `targets/_common/__init__.py` | NEW | 5 |
| `targets/_common/skills.py` | NEW | ~30 |
| `targets/_common/mcp_bundling.py` | NEW | ~80 |
| `targets/_common/manifest.py` | NEW | ~30 |
| `targets/claude-code/build.py` | REFACTOR | ~100 |
| `targets/codex/build.py` | REWRITE | ~120 |
| `targets/gemini-cli/build.py` | NEW | ~100 |
| `targets/gemini-cli/README.md` | NEW | ~30 |
| `targets/cursor/build.py` | NEW | ~100 |
| `targets/cursor/README.md` | NEW | ~30 |
| `targets/copilot/build.py` | NEW | ~100 |
| `targets/copilot/README.md` | NEW | ~30 |
| `targets/antigravity/build.py` | NEW | ~80 |
| `targets/antigravity/README.md` | NEW | ~30 |
| `targets/claude-desktop/build.py` | REFACTOR | ~80 |

### New test files

```
tests/targets/_common/
├── __init__.py
├── test_skills_helper.py
└── test_mcp_bundling_helper.py

tests/targets/codex/
├── __init__.py
├── conftest.py
├── test_build_runs.py
├── test_manifest.py
├── test_skills_copied.py
├── test_mcp_servers_bundled.py
├── test_config_toml.py
└── test_no_hooks.py

tests/targets/gemini_cli/   (same pattern, +test_extension_json.py +test_commands.py)
tests/targets/cursor/       (same pattern + test_commands.py)
tests/targets/copilot/      (same pattern + test_commands.py + test_servers_key.py)
tests/targets/antigravity/  (same pattern, replaces test_manifest.py with test_no_manifest.py + test_workflow.py)
tests/targets/claude_desktop/ (same pattern, replaces manifest with test_concatenated_skills.py)

tests/targets/test_all_targets_buildable.py   # cross-target smoke
```

### Doc updates

- `docs/adding-targets.md` — refresh with current host list + standard skeleton
- `targets/<name>/README.md` — per-target build instructions (5 new + 1 update)

---

## Phase 1: Shared helpers

### Task 1: `targets/_common/skills.py` + tests

**Files:**
- Create: `targets/_common/__init__.py`
- Create: `targets/_common/skills.py`
- Create: `tests/targets/_common/__init__.py`
- Create: `tests/targets/_common/test_skills_helper.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/targets/_common/test_skills_helper.py
from pathlib import Path

import pytest

from targets._common.skills import INCLUDED_SKILLS, copy_skills


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def test_included_skills_set():
    assert INCLUDED_SKILLS == frozenset({
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    })


def test_skill_refiner_not_included():
    assert "skill-refiner" not in INCLUDED_SKILLS


def test_copy_skills_creates_dir_and_returns_names(tmp_path):
    out = tmp_path / "skills"
    names = copy_skills(SRC_ROOT, out)
    assert sorted(names) == sorted(INCLUDED_SKILLS)
    for name in names:
        assert (out / name / "SKILL.md").is_file()
    # Refiner explicitly absent
    assert not (out / "skill-refiner").exists()


def test_copy_skills_raises_on_missing_source(tmp_path):
    bad_src = tmp_path / "nope"
    bad_src.mkdir()
    with pytest.raises(RuntimeError):
        copy_skills(bad_src, tmp_path / "out")
```

- [ ] **Step 2: Run, verify failure**

```bash
.venv/bin/pytest tests/targets/_common/test_skills_helper.py -v
```

Expected: ImportError / ModuleNotFoundError.

- [ ] **Step 3: Implement `targets/_common/skills.py`**

```python
# targets/_common/__init__.py — empty marker
```

```python
# targets/_common/skills.py
"""Shared cycle-3 skills allowlist + copy helper used by every build target."""
from __future__ import annotations

import shutil
from pathlib import Path


INCLUDED_SKILLS = frozenset({
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
})


def copy_skills(src_root: Path, dst_skills_dir: Path) -> list[str]:
    """Copy each cycle-3 skill from `src_root/skills/<name>/` into
    `dst_skills_dir/<name>/`. Excludes `skill-refiner` (cycle 6).

    Creates `dst_skills_dir` if missing.

    Returns the list of skill names copied.
    Raises RuntimeError if any allowlisted skill is missing from the source.
    """
    skills_src = src_root / "skills"
    if not skills_src.is_dir():
        raise RuntimeError(f"skills source missing: {skills_src}")
    dst_skills_dir.mkdir(parents=True, exist_ok=True)
    copied: list[str] = []
    for name in sorted(INCLUDED_SKILLS):
        src = skills_src / name
        if not src.is_dir():
            raise RuntimeError(f"missing skill source: {src}")
        shutil.copytree(src, dst_skills_dir / name)
        copied.append(name)
    return copied
```

- [ ] **Step 4: Verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add targets/_common/__init__.py targets/_common/skills.py \
        tests/targets/_common/__init__.py tests/targets/_common/test_skills_helper.py
git commit -m "cycle-7 task 1: targets/_common/skills.py — allowlist + copy helper"
```

---

### Task 2: `targets/_common/mcp_bundling.py` + tests

**Files:**
- Create: `targets/_common/mcp_bundling.py`
- Create: `tests/targets/_common/test_mcp_bundling_helper.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/targets/_common/test_mcp_bundling_helper.py
from pathlib import Path

import pytest

from targets._common.mcp_bundling import MCP_SERVERS, bundle_mcp_servers


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"


def test_mcp_servers_descriptors():
    names = {s["external_name"] for s in MCP_SERVERS}
    assert names == {"netcdf-reader", "plot-renderer"}
    for s in MCP_SERVERS:
        assert "package_dir" in s
        assert "external_name" in s
        assert "entry_point" in s


def test_bundle_creates_re_rooted_source(tmp_path):
    bundle_mcp_servers(SRC_ROOT, tmp_path)
    for s in MCP_SERVERS:
        bundled = tmp_path / s["package_dir"] / "src" / "mcp" / s["package_dir"]
        assert bundled.is_dir(), f"missing re-rooted package: {bundled}"
        assert (bundled / "__init__.py").is_file()
        assert (bundled / "server.py").is_file()


def test_bundle_patches_pyproject(tmp_path):
    bundle_mcp_servers(SRC_ROOT, tmp_path)
    for s in MCP_SERVERS:
        pp = tmp_path / s["package_dir"] / "pyproject.toml"
        assert pp.is_file()
        text = pp.read_text()
        assert "[tool.setuptools.packages.find]" in text
        assert 'where = ["src"]' in text


def test_bundle_returns_descriptor_list(tmp_path):
    result = bundle_mcp_servers(SRC_ROOT, tmp_path)
    assert isinstance(result, list)
    assert {r["external_name"] for r in result} == {
        "netcdf-reader", "plot-renderer"}
```

- [ ] **Step 2: Run, verify failure (ImportError)**

- [ ] **Step 3: Implement `targets/_common/mcp_bundling.py`**

```python
# targets/_common/mcp_bundling.py
"""Shared MCP server bundling helper used by every build target.

Re-roots the canonical `src/mcp/<name>/` source under
`<dst_root>/<name>/src/mcp/<name>/` so the `from src.mcp.<name>...`
import path used in server.py continues to work after `pip install`
from the bundled location. Patches pyproject.toml to enable
setuptools.packages.find against the bundled `src/` directory.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


MCP_SERVERS = [
    {
        "package_dir": "netcdf_reader",
        "external_name": "netcdf-reader",
        "entry_point": "ncplot-netcdf-reader",
    },
    {
        "package_dir": "plot_renderer",
        "external_name": "plot-renderer",
        "entry_point": "ncplot-plot-renderer",
    },
]


def bundle_mcp_servers(src_root: Path, dst_root: Path) -> list[dict[str, Any]]:
    """Bundle each MCP server into `dst_root/<package_dir>/`.

    Returns the MCP_SERVERS list (passed through, for symmetry with
    callers that want a single function to both bundle and discover).
    """
    dst_root.mkdir(parents=True, exist_ok=True)
    for server in MCP_SERVERS:
        pkg_dir = server["package_dir"]
        src = src_root / "mcp" / pkg_dir
        if not src.is_dir():
            raise RuntimeError(f"missing MCP server source: {src}")
        dst = dst_root / pkg_dir
        dst.mkdir()

        # Re-root: <dst>/src/mcp/<pkg_dir>/ ← copy of <src>/
        bundled_src = dst / "src" / "mcp" / pkg_dir
        bundled_src.parent.mkdir(parents=True)
        shutil.copytree(src, bundled_src)

        # Patch pyproject.toml
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

    return list(MCP_SERVERS)
```

- [ ] **Step 4: Verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add targets/_common/mcp_bundling.py \
        tests/targets/_common/test_mcp_bundling_helper.py
git commit -m "cycle-7 task 2: targets/_common/mcp_bundling.py — re-rooted source bundler"
```

---

### Task 3: `targets/_common/manifest.py` constants

**Files:**
- Create: `targets/_common/manifest.py`

This module holds shared metadata constants. No tests needed — it's
just data that other tests will pull from.

- [ ] **Step 1: Write the file**

```python
# targets/_common/manifest.py
"""Shared metadata constants used by every build target."""
from __future__ import annotations

from targets._common.skills import INCLUDED_SKILLS
from targets._common.mcp_bundling import MCP_SERVERS


PLUGIN_NAME = "ncplot-agent"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = (
    "Natural-language plotting from NetCDF files. Maps, time series, "
    "and vertical profiles. WRF/ROMS/CMIP/reanalysis aware."
)
PLUGIN_HOMEPAGE = "https://github.com/grnydawn/ncplot-agent"
PLUGIN_LICENSE = "MIT"
PLUGIN_KEYWORDS = ["netcdf", "matplotlib", "cartopy", "wrf", "roms",
                    "cmip", "climate"]
PLUGIN_AUTHOR = {"name": "ncplot-agent contributors"}


def common_ncplot_block(build_cycle: int) -> dict:
    """Return the `ncplot` namespace block for embedding in any
    host-specific manifest. All host manifests carry this block for
    cross-target audit."""
    return {
        "build_cycle": build_cycle,
        "ships_skills": sorted(INCLUDED_SKILLS),
        "ships_mcp_servers": [s["external_name"] for s in MCP_SERVERS],
    }
```

- [ ] **Step 2: Verify imports work**

```bash
.venv/bin/python -c "
from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, common_ncplot_block,
)
print(PLUGIN_NAME, PLUGIN_VERSION)
print(common_ncplot_block(7))
"
```

Expected: prints constants and the cycle-7 ncplot block.

- [ ] **Step 3: Commit**

```bash
git add targets/_common/manifest.py
git commit -m "cycle-7 task 3: targets/_common/manifest.py — shared metadata constants"
```

---

## Phase 2: Refactor Claude Code to use shared helpers

### Task 4: Refactor `targets/claude-code/build.py`

Behavior identical; cycle-4 tests must pass unchanged.

**Files:**
- Modify: `targets/claude-code/build.py`

- [ ] **Step 1: Refactor (replace existing implementation with shared-helpers version)**

```python
"""Build the Claude Code plugin from src/.

Cycle 4 baseline: produces a payload at `build/claude-code/ncplot-agent/`
with skills, bundled MCP servers, .mcp.json, and a placeholder /refine
command.

Cycle 7: refactored to use targets/_common helpers. Behavior identical.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_KEYWORDS, PLUGIN_AUTHOR,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    """Build the Claude Code plugin into `out_root/<PLUGIN_NAME>/`."""
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # Manifest
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir()
    manifest = {
        "$schema": "https://json.schemastore.org/claude-code-plugin",
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "keywords": PLUGIN_KEYWORDS,
        "ncplot": common_ncplot_block(build_cycle=4),
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    # Skills
    copy_skills(src_root, plugin_dir / "skills")

    # MCP servers
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # MCP launch config
    mcp_servers = {
        s["external_name"]: {"command": s["entry_point"], "args": []}
        for s in MCP_SERVERS
    }
    (plugin_dir / ".mcp.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n")

    # Slash command
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(_refine_command_md())

    # Plugin README
    (plugin_dir / "README.md").write_text(
        _plugin_readme(included_skills=sorted({
            s for s in (plugin_dir / "skills").iterdir() if s.is_dir()
        }, key=lambda p: p.name) if False else []))

    # Note: we re-read the skills dir we just wrote to populate the
    # README; switch to the helper return value instead.
    skills_in_build = sorted([p.name for p in (plugin_dir / "skills").iterdir()
                               if p.is_dir()])
    mcps_in_build = [s["external_name"] for s in MCP_SERVERS]
    (plugin_dir / "README.md").write_text(
        _plugin_readme_full(skills_in_build, mcps_in_build))


def _refine_command_md() -> str:
    return (
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


def _plugin_readme_full(skills: list[str], mcps: list[str]) -> str:
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps)
    mcp_install = "\n".join(
        f"pip install ./mcp-servers/{s['package_dir']}"
        for s in MCP_SERVERS
    )
    return (
        "# ncplot-agent — Claude Code plugin\n\n"
        "NetCDF plotting via natural language. Maps, time series, and "
        "vertical profiles. WRF/ROMS/CMIP/reanalysis aware.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n" + mcp_install + "\n```\n\n"
        "### 2. Install the plugin\n\n"
        "```bash\ncp -r . ~/.claude/plugins/ncplot-agent\n```\n\n"
        "### 3. Restart Claude Code\n\n"
        "## What's inside\n\nSkills:\n" + skill_lines + "\n\n"
        "MCP servers:\n" + mcp_lines + "\n\n"
        "Slash commands:\n  - `/refine` — placeholder (cycle 6)\n\n"
        "Hooks: none (cycle 6 will add).\n\n"
        "## Build provenance\n\n"
        "Built by `targets/claude-code/build.py` from `src/`. Rebuild with:\n\n"
        "```bash\npython -m tools.build claude-code\n```\n"
    )


# Backwards-compat re-export for tests that imported PLUGIN_NAME directly
__all__ = ["PLUGIN_NAME", "build"]
```

- [ ] **Step 2: Run cycle-4 tests to confirm no regression**

```bash
.venv/bin/python -m tools.build claude-code --validate
```

Expected: build runs, all cycle-4 tests pass.

- [ ] **Step 3: Commit**

```bash
git add targets/claude-code/build.py
git commit -m "cycle-7 task 4: refactor claude-code build.py to use targets/_common"
```

---

## Phase 3: Codex CLI/Desktop target

### Task 5: `targets/codex/build.py` rewrite

**Files:**
- Modify: `targets/codex/build.py` (currently an AGENTS.md stub)
- Modify: `targets/codex/README.md`

- [ ] **Step 1: Verify `tomli_w` is installed; install if not**

```bash
.venv/bin/python -c "import tomli_w" 2>&1 || .venv/bin/python -m pip install tomli_w
```

(If `pip` not on PATH inside the venv, use `uv pip install --python .venv/bin/python tomli_w`.)

- [ ] **Step 2: Write the new build.py**

```python
"""Build the Codex CLI/Desktop plugin from src/.

Codex's plugin format: `.codex-plugin/plugin.json` manifest at the root,
`skills/<name>/SKILL.md` directly (Codex loads SKILL.md natively as of
2026), and MCP servers configured in `config.toml` (TOML format —
distinct from Claude Code's JSON).

Codex Desktop shares the format; one target covers both.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import tomli_w

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_KEYWORDS, PLUGIN_AUTHOR,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # .codex-plugin/plugin.json manifest
    manifest_dir = plugin_dir / ".codex-plugin"
    manifest_dir.mkdir()
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "keywords": PLUGIN_KEYWORDS,
        "ncplot": common_ncplot_block(build_cycle=7),
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    # Skills (Codex loads SKILL.md from skills/ natively)
    copy_skills(src_root, plugin_dir / "skills")

    # MCP servers (re-rooted source + patched pyproject)
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # config.toml — Codex MCP launch stanzas in TOML format
    config_doc = {
        "mcp_servers": {
            s["external_name"]: {
                "type": "stdio",
                "command": s["entry_point"],
                "args": [],
            }
            for s in MCP_SERVERS
        }
    }
    (plugin_dir / "config.toml").write_bytes(tomli_w.dumps(config_doc).encode())

    # Plugin README
    (plugin_dir / "README.md").write_text(_plugin_readme())


def _plugin_readme() -> str:
    skills = sorted([
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    ])
    mcps = ["netcdf-reader", "plot-renderer"]
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps)
    return (
        "# ncplot-agent — Codex plugin\n\n"
        "NetCDF plotting via natural language. Maps, time series, and "
        "vertical profiles.\n\n"
        "Works in Codex CLI and Codex Desktop (shared plugin format).\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "Copy this directory under your Codex plugin search path "
        "(typically `~/.codex/plugins/ncplot-agent/`), or follow the "
        "Codex marketplace install flow if available.\n\n"
        "### 3. Merge config.toml into your Codex config\n\n"
        "Append the contents of `config.toml` to `~/.codex/config.toml` "
        "(or your project-scoped `.codex/config.toml`).\n\n"
        "### 4. Restart Codex CLI / Desktop\n\n"
        "## What's inside\n\nSkills:\n" + skill_lines + "\n\n"
        "MCP servers:\n" + mcp_lines + "\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **No custom slash command.** Codex's user-defined `/foo` "
        "authoring format is undocumented as of May 2026; we omit a "
        "`/refine` command. To trigger refinement (cycle 6), use the "
        "skill-refiner skill directly.\n"
        "- **No hooks.** Cycle-6 self-improvement Stop hook will be "
        "added in a follow-up.\n"
    )
```

- [ ] **Step 3: Smoke test**

```bash
.venv/bin/python -m tools.build codex
ls build/codex/ncplot-agent/
cat build/codex/ncplot-agent/.codex-plugin/plugin.json
cat build/codex/ncplot-agent/config.toml
ls build/codex/ncplot-agent/skills/
```

Expected: `.codex-plugin/plugin.json`, `skills/` with 5 dirs, `mcp-servers/`, `config.toml` with both servers, `README.md`.

- [ ] **Step 4: Commit**

```bash
git add targets/codex/build.py
git commit -m "cycle-7 task 5: codex build.py — native SKILL.md + config.toml MCP"
```

---

### Task 6: `tests/targets/codex/`

**Files:**
- Create: `tests/targets/codex/__init__.py`
- Create: `tests/targets/codex/conftest.py`
- Create: `tests/targets/codex/test_build_runs.py`
- Create: `tests/targets/codex/test_manifest.py`
- Create: `tests/targets/codex/test_skills_copied.py`
- Create: `tests/targets/codex/test_mcp_servers_bundled.py`
- Create: `tests/targets/codex/test_config_toml.py`
- Create: `tests/targets/codex/test_no_hooks.py`

- [ ] **Step 1: Create empty markers + conftest**

```python
# tests/targets/codex/__init__.py — empty
```

```python
# tests/targets/codex/conftest.py
"""Build the Codex plugin into a tmp dir; module-scoped fixture."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "codex" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "targets.codex.build", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("build-codex")
    mod = _load_build_module()
    mod.build(SRC_ROOT, out)
    plugin_root = out / "ncplot-agent"
    assert plugin_root.is_dir()
    return plugin_root


@pytest.fixture(scope="module")
def build_module():
    return _load_build_module()
```

- [ ] **Step 2: Write `test_build_runs.py`**

```python
# tests/targets/codex/test_build_runs.py
from pathlib import Path


def test_plugin_root_exists(built_plugin: Path):
    assert built_plugin.is_dir()
    assert built_plugin.name == "ncplot-agent"


def test_manifest_dir_present(built_plugin: Path):
    assert (built_plugin / ".codex-plugin" / "plugin.json").is_file()


def test_top_level_present(built_plugin: Path):
    for f in ("config.toml", "README.md"):
        assert (built_plugin / f).is_file(), f"missing {f}"
    for d in ("skills", "mcp-servers"):
        assert (built_plugin / d).is_dir(), f"missing dir {d}"


def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()
```

- [ ] **Step 3: Write `test_manifest.py`**

```python
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
```

- [ ] **Step 4: Write `test_skills_copied.py`**

```python
# tests/targets/codex/test_skills_copied.py
from pathlib import Path

import pytest


_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}


def test_all_expected_skills_present(built_plugin: Path):
    actual = {p.name for p in (built_plugin / "skills").iterdir() if p.is_dir()}
    assert actual == _EXPECTED


def test_skill_refiner_excluded(built_plugin: Path):
    assert not (built_plugin / "skills" / "skill-refiner").exists()


@pytest.mark.parametrize("skill", sorted(_EXPECTED))
def test_skill_md_present(built_plugin: Path, skill: str):
    assert (built_plugin / "skills" / skill / "SKILL.md").is_file()
```

- [ ] **Step 5: Write `test_mcp_servers_bundled.py`**

```python
# tests/targets/codex/test_mcp_servers_bundled.py
from pathlib import Path

import pytest


_SERVERS = ("netcdf_reader", "plot_renderer")


@pytest.mark.parametrize("server", _SERVERS)
def test_re_rooted_source(built_plugin: Path, server: str):
    pkg = built_plugin / "mcp-servers" / server / "src" / "mcp" / server
    assert pkg.is_dir()
    assert (pkg / "server.py").is_file()


@pytest.mark.parametrize("server", _SERVERS)
def test_pyproject_patched(built_plugin: Path, server: str):
    text = (built_plugin / "mcp-servers" / server / "pyproject.toml").read_text()
    assert "[tool.setuptools.packages.find]" in text
    assert 'where = ["src"]' in text
```

- [ ] **Step 6: Write `test_config_toml.py`**

```python
# tests/targets/codex/test_config_toml.py
import sys
from pathlib import Path

import pytest

# Python 3.11+ has tomllib; fall back to tomli for 3.10
if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


def _load(p: Path) -> dict:
    return tomllib.loads(p.read_text())


def test_parses_as_toml(built_plugin: Path):
    _load(built_plugin / "config.toml")


def test_has_mcp_servers_section(built_plugin: Path):
    d = _load(built_plugin / "config.toml")
    assert "mcp_servers" in d


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "ncplot-netcdf-reader"),
     ("plot-renderer", "ncplot-plot-renderer")],
)
def test_each_server_uses_entry_point(
    built_plugin: Path, external_name: str, entry_point: str,
):
    d = _load(built_plugin / "config.toml")
    s = d["mcp_servers"][external_name]
    assert s["type"] == "stdio"
    assert s["command"] == entry_point
    assert s["args"] == []
```

- [ ] **Step 7: Write `test_no_hooks.py`**

```python
# tests/targets/codex/test_no_hooks.py
from pathlib import Path
import json


def test_no_hooks_dir(built_plugin: Path):
    """Codex hooks land with skill-refiner in cycle 6."""
    assert not (built_plugin / "hooks").exists()


def test_manifest_has_no_hooks(built_plugin: Path):
    m = json.loads((built_plugin / ".codex-plugin" / "plugin.json").read_text())
    assert "hooks" not in m or not m["hooks"]
```

- [ ] **Step 8: Run all Codex tests**

```bash
.venv/bin/pytest tests/targets/codex -v
```

Expected: all pass (~25 tests).

- [ ] **Step 9: Commit**

```bash
git add tests/targets/codex/
git commit -m "cycle-7 task 6: codex test suite (manifest, skills, MCP, config.toml, no-hooks)"
```

---

## Phase 4: Gemini CLI target

### Task 7: `targets/gemini-cli/build.py`

**Files:**
- Create: `targets/gemini-cli/__init__.py` (empty marker — wait, targets/<name>/ aren't Python packages; skip)
- Create: `targets/gemini-cli/build.py`
- Create: `targets/gemini-cli/README.md`

The directory is hyphenated to match the host's natural name. The build.py is loaded by spec-loader (no Python import path).

- [ ] **Step 1: Write `targets/gemini-cli/build.py`**

```python
"""Build the Gemini CLI extension from src/.

Gemini CLI loads `gemini-extension.json` at the root of an extension,
discovers `skills/` natively, reads MCP servers from `settings.json`,
and runs slash commands from `commands/<name>.toml`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # gemini-extension.json (root manifest)
    extension_manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "homepage": PLUGIN_HOMEPAGE,
        "skills": "skills",
        "commands": "commands",
        "ncplot": common_ncplot_block(build_cycle=7),
    }
    (plugin_dir / "gemini-extension.json").write_text(
        json.dumps(extension_manifest, indent=2) + "\n")

    # Skills
    copy_skills(src_root, plugin_dir / "skills")

    # MCP servers
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # settings.json — MCP launch stanzas (Gemini reads this)
    settings = {
        "mcpServers": {
            s["external_name"]: {
                "command": s["entry_point"],
                "args": [],
            }
            for s in MCP_SERVERS
        }
    }
    (plugin_dir / "settings.json").write_text(
        json.dumps(settings, indent=2) + "\n")

    # commands/refine.toml
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.toml").write_text(_refine_toml())

    # Plugin README
    (plugin_dir / "README.md").write_text(_plugin_readme())


def _refine_toml() -> str:
    return (
        'description = "Review the current session and propose refinement '
        'drafts to the canonical skills. (Placeholder — full implementation '
        'in cycle 6.)"\n'
        'prompt = "The /refine command is a placeholder until cycle 6 ships '
        'the skill-refiner skill. Until then: skills are appending corrections '
        'to .ncplot/task-log.jsonl, but no automatic refinement happens."\n'
    )


def _plugin_readme() -> str:
    skills = sorted([
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    ])
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    return (
        "# ncplot-agent — Gemini CLI extension\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the extension\n\n"
        "From a Git checkout:\n\n"
        "```bash\n"
        "gemini extensions install <git-url-or-path>\n"
        "```\n\n"
        "Or copy this directory to `~/.gemini/extensions/ncplot-agent/`.\n\n"
        "### 3. Merge settings.json into your Gemini settings\n\n"
        "The MCP launch stanzas need to land in `~/.gemini/settings.json` "
        "(global) or `.gemini/settings.json` (project). Use a JSON merge "
        "tool or copy the `mcpServers` block into your existing settings.\n\n"
        "### 4. Restart Gemini CLI\n\n"
        "## What's inside\n\nSkills:\n" + skill_lines + "\n\n"
        "Slash commands:\n  - `/refine` — placeholder (cycle 6)\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Gemini's `SessionEnd` hook will "
        "trigger the skill-refiner once it ships.\n"
    )
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m tools.build gemini-cli 2>&1 | head -10
ls build/gemini-cli/ncplot-agent/
cat build/gemini-cli/ncplot-agent/gemini-extension.json
cat build/gemini-cli/ncplot-agent/settings.json
cat build/gemini-cli/ncplot-agent/commands/refine.toml
```

Expected: extension manifest, settings with both MCP servers, TOML refine command.

- [ ] **Step 3: Commit**

```bash
git add targets/gemini-cli/build.py
git commit -m "cycle-7 task 7: gemini-cli build.py — native SKILL.md + settings.json MCP + TOML commands"
```

---

### Task 8: `tests/targets/gemini_cli/`

Mirror the codex test suite structure. Replace `test_config_toml.py` with `test_settings_json.py` (and add `test_extension_json.py` for the root manifest, `test_commands.py` for the TOML slash command).

**Files:**
- Create: `tests/targets/gemini_cli/__init__.py`
- Create: `tests/targets/gemini_cli/conftest.py`
- Create: `tests/targets/gemini_cli/test_build_runs.py`
- Create: `tests/targets/gemini_cli/test_extension_json.py`
- Create: `tests/targets/gemini_cli/test_skills_copied.py`
- Create: `tests/targets/gemini_cli/test_mcp_servers_bundled.py`
- Create: `tests/targets/gemini_cli/test_settings_json.py`
- Create: `tests/targets/gemini_cli/test_commands.py`
- Create: `tests/targets/gemini_cli/test_no_hooks.py`

- [ ] **Step 1: Write conftest (mirror codex/conftest.py with paths swapped)**

```python
# tests/targets/gemini_cli/conftest.py
import importlib.util
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "gemini-cli" / "build.py"


def _load_build_module():
    spec = importlib.util.spec_from_file_location(
        "targets.gemini_cli.build", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory) -> Path:
    out = tmp_path_factory.mktemp("build-gemini-cli")
    mod = _load_build_module()
    mod.build(SRC_ROOT, out)
    return out / "ncplot-agent"
```

- [ ] **Step 2: Write the 6 test files (use the codex equivalents as templates; key differences below)**

`test_build_runs.py`: assert `gemini-extension.json`, `settings.json`, `commands/`, `README.md`, `skills/`, `mcp-servers/`. No hooks dir.

`test_extension_json.py`:
```python
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
```

`test_skills_copied.py`: copy from codex test verbatim.

`test_mcp_servers_bundled.py`: copy from codex test verbatim.

`test_settings_json.py`:
```python
import json
from pathlib import Path
import pytest

def test_settings_parses(built_plugin: Path):
    json.loads((built_plugin / "settings.json").read_text())

def test_has_mcp_servers_key(built_plugin: Path):
    d = json.loads((built_plugin / "settings.json").read_text())
    assert "mcpServers" in d

@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "ncplot-netcdf-reader"),
     ("plot-renderer", "ncplot-plot-renderer")],
)
def test_each_server_entry_point(built_plugin: Path, external_name: str, entry_point: str):
    d = json.loads((built_plugin / "settings.json").read_text())
    s = d["mcpServers"][external_name]
    assert s["command"] == entry_point
```

`test_commands.py`:
```python
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
```

`test_no_hooks.py`: copy from codex equivalent.

- [ ] **Step 3: Run**

```bash
.venv/bin/pytest tests/targets/gemini_cli -v
```

Expected: all pass.

- [ ] **Step 4: Commit**

```bash
git add tests/targets/gemini_cli/
git commit -m "cycle-7 task 8: gemini-cli test suite"
```

---

## Phase 5: Cursor target

### Task 9: `targets/cursor/build.py`

**Files:**
- Create: `targets/cursor/build.py`
- Create: `targets/cursor/README.md`

- [ ] **Step 1: Write the build.py**

```python
"""Build the Cursor plugin from src/.

Cursor's plugin format: `.cursor-plugin/plugin.json` manifest,
`skills/<name>/SKILL.md`, `.cursor/mcp.json` for MCP launch (same
shape as Claude Code's `.mcp.json` — uses `mcpServers` key),
`commands/<name>.md` for slash commands (same as Claude Code).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_AUTHOR,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    manifest_dir = plugin_dir / ".cursor-plugin"
    manifest_dir.mkdir()
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "ncplot": common_ncplot_block(build_cycle=7),
    }
    (manifest_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    copy_skills(src_root, plugin_dir / "skills")
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # .cursor/mcp.json (Cursor-specific path; same shape as Claude Code's .mcp.json)
    cursor_dir = plugin_dir / ".cursor"
    cursor_dir.mkdir()
    mcp_servers = {
        s["external_name"]: {"command": s["entry_point"], "args": []}
        for s in MCP_SERVERS
    }
    (cursor_dir / "mcp.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n")

    # commands/refine.md (same format as Claude Code's)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(_refine_md())

    (plugin_dir / "README.md").write_text(_plugin_readme())


def _refine_md() -> str:
    return (
        "---\n"
        "description: Review the current session and propose refinement drafts. "
        "(Placeholder — cycle 6.)\n"
        "---\n\n"
        "Placeholder for the cycle-6 skill-refiner trigger. Skills are "
        "writing `.ncplot/task-log.jsonl` on user corrections; cycle 6 "
        "will read that and produce refinement drafts.\n"
    )


def _plugin_readme() -> str:
    return (
        "# ncplot-agent — Cursor plugin\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "Copy this directory to `~/.cursor/plugins/ncplot-agent/`, "
        "or use the Cursor Marketplace install flow.\n\n"
        "### 3. Restart Cursor\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Cursor's `stop` hook (camelCase) "
        "will trigger skill-refiner once it ships.\n"
    )
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m tools.build cursor 2>&1 | head
ls build/cursor/ncplot-agent/
ls build/cursor/ncplot-agent/.cursor/
```

- [ ] **Step 3: Commit**

```bash
git add targets/cursor/build.py
git commit -m "cycle-7 task 9: cursor build.py — .cursor-plugin manifest + .cursor/mcp.json"
```

---

### Task 10: `tests/targets/cursor/`

Same pattern as codex tests but adapted for Cursor's manifest/MCP paths. Files: `__init__.py`, `conftest.py`, `test_build_runs.py`, `test_manifest.py`, `test_skills_copied.py`, `test_mcp_servers_bundled.py`, `test_mcp_json.py` (asserts `.cursor/mcp.json`), `test_commands.py` (asserts `commands/refine.md`), `test_no_hooks.py`.

- [ ] **Step 1: Write conftest (paths swapped to cursor)**

```python
# tests/targets/cursor/conftest.py
import importlib.util
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
BUILD_PY = REPO_ROOT / "targets" / "cursor" / "build.py"


def _load():
    spec = importlib.util.spec_from_file_location("targets.cursor.build", BUILD_PY)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def built_plugin(tmp_path_factory):
    out = tmp_path_factory.mktemp("build-cursor")
    _load().build(SRC_ROOT, out)
    return out / "ncplot-agent"
```

- [ ] **Step 2: Write the 7 test files** (mirror codex/gemini equivalents; key tests below)

`test_build_runs.py`: assert `.cursor-plugin/plugin.json`, `.cursor/mcp.json`, `commands/refine.md`, `README.md`, `skills/`, `mcp-servers/`. No hooks dir.

`test_manifest.py`:
```python
import json
from pathlib import Path

def test_parses(built_plugin: Path):
    json.loads((built_plugin / ".cursor-plugin" / "plugin.json").read_text())

def test_required_fields(built_plugin: Path):
    m = json.loads((built_plugin / ".cursor-plugin" / "plugin.json").read_text())
    for f in ("name", "version", "description"): assert f in m

def test_ncplot_cycle_7(built_plugin: Path):
    m = json.loads((built_plugin / ".cursor-plugin" / "plugin.json").read_text())
    assert m["ncplot"]["build_cycle"] == 7
```

`test_skills_copied.py`, `test_mcp_servers_bundled.py`: copy from codex tests.

`test_mcp_json.py`:
```python
import json
from pathlib import Path
import pytest

def test_at_cursor_subdir(built_plugin: Path):
    assert (built_plugin / ".cursor" / "mcp.json").is_file()

def test_uses_mcpServers_key(built_plugin: Path):
    """Cursor uses mcpServers (same as Claude Code), NOT 'servers' (Copilot)."""
    d = json.loads((built_plugin / ".cursor" / "mcp.json").read_text())
    assert "mcpServers" in d
    assert "servers" not in d

@pytest.mark.parametrize("external_name,entry_point",
    [("netcdf-reader", "ncplot-netcdf-reader"),
     ("plot-renderer", "ncplot-plot-renderer")])
def test_entry_point(built_plugin: Path, external_name: str, entry_point: str):
    d = json.loads((built_plugin / ".cursor" / "mcp.json").read_text())
    assert d["mcpServers"][external_name]["command"] == entry_point
```

`test_commands.py`:
```python
from pathlib import Path

def test_refine_md_present(built_plugin: Path):
    assert (built_plugin / "commands" / "refine.md").is_file()

def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert text.startswith("---\n")

def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / "commands" / "refine.md").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()
```

`test_no_hooks.py`: copy from codex equivalent.

- [ ] **Step 3: Run + commit**

```bash
.venv/bin/pytest tests/targets/cursor -v
git add tests/targets/cursor/
git commit -m "cycle-7 task 10: cursor test suite"
```

---

## Phase 6: GitHub Copilot target

### Task 11: `targets/copilot/build.py`

**KEY GOTCHA:** Copilot's `.vscode/mcp.json` uses `servers` (not `mcpServers`).

**Files:**
- Create: `targets/copilot/build.py`
- Create: `targets/copilot/README.md`

- [ ] **Step 1: Write the build.py**

```python
"""Build the GitHub Copilot agent plugin from src/.

Copilot's plugin format: `plugin.json` at the root (NOT in a subdir),
`skills/<name>/SKILL.md`, `.vscode/mcp.json` for MCP — uses
`servers` key (NOT `mcpServers`! the gotcha noted in the cycle-7 spec),
`commands/<name>.md` for slash commands.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_AUTHOR,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # plugin.json at root (Copilot convention; not under a .copilot-plugin dir)
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "ncplot": common_ncplot_block(build_cycle=7),
    }
    (plugin_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    copy_skills(src_root, plugin_dir / "skills")
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # .vscode/mcp.json — IMPORTANT: uses "servers" key, not "mcpServers"
    # This is the only host that uses this naming. Don't refactor it.
    vscode_dir = plugin_dir / ".vscode"
    vscode_dir.mkdir()
    servers = {
        s["external_name"]: {"command": s["entry_point"], "args": []}
        for s in MCP_SERVERS
    }
    (vscode_dir / "mcp.json").write_text(
        json.dumps({"servers": servers}, indent=2) + "\n")

    # commands/refine.md (same shape as Claude Code's)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(
        "---\n"
        "description: Review the current session and propose refinement drafts. "
        "(Placeholder — cycle 6.)\n"
        "---\n\n"
        "Placeholder for cycle-6 skill-refiner.\n"
    )

    (plugin_dir / "README.md").write_text(_plugin_readme())


def _plugin_readme() -> str:
    return (
        "# ncplot-agent — GitHub Copilot agent plugin\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "From VS Code: Chat → Install Plugin From Source → select this directory.\n\n"
        "Or copy to `~/.copilot/plugins/ncplot-agent/`.\n\n"
        "### 3. Restart VS Code\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Copilot's `Stop` hook (PascalCase) "
        "will trigger skill-refiner once it ships.\n"
        "- **Plugin system in Preview.** Some rough edges expected as of "
        "May 2026.\n"
    )
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m tools.build copilot
cat build/copilot/ncplot-agent/.vscode/mcp.json
```

Expected: file uses `"servers"` (not `"mcpServers"`).

- [ ] **Step 3: Commit**

```bash
git add targets/copilot/build.py
git commit -m "cycle-7 task 11: copilot build.py — plugin.json at root + .vscode/mcp.json with 'servers' key"
```

---

### Task 12: `tests/targets/copilot/`

**Crucial test:** `test_servers_key.py` asserts `.vscode/mcp.json` uses `servers` (not `mcpServers`). This catches the most likely cross-target bug.

**Files:** mirror previous targets; key files below.

- [ ] **Step 1: conftest.py** (mirror cursor's, paths swapped)

- [ ] **Step 2: test_build_runs.py**

```python
from pathlib import Path

def test_plugin_root(built_plugin: Path):
    assert built_plugin.is_dir()

def test_manifest_at_root(built_plugin: Path):
    """Copilot manifest is at the root, NOT in a subdirectory."""
    assert (built_plugin / "plugin.json").is_file()
    assert not (built_plugin / ".copilot-plugin").exists()
    assert not (built_plugin / ".claude-plugin").exists()

def test_vscode_dir_present(built_plugin: Path):
    assert (built_plugin / ".vscode" / "mcp.json").is_file()

def test_no_hooks_dir(built_plugin: Path):
    assert not (built_plugin / "hooks").exists()
```

- [ ] **Step 3: test_servers_key.py** (the cycle-7 trap)

```python
"""IMPORTANT: Copilot's .vscode/mcp.json uses `servers` key, not `mcpServers`.

This is the only host with this naming. Other targets use `mcpServers`.
If this test ever fails, check for cross-target copy-paste contamination.
"""
import json
from pathlib import Path

import pytest


def test_uses_servers_not_mcpServers(built_plugin: Path):
    d = json.loads((built_plugin / ".vscode" / "mcp.json").read_text())
    assert "servers" in d, "Copilot expects 'servers' key in .vscode/mcp.json"
    assert "mcpServers" not in d, (
        "Copilot does NOT use 'mcpServers' (that's Claude Code / Cursor / "
        "Gemini convention)")


@pytest.mark.parametrize(
    "external_name,entry_point",
    [("netcdf-reader", "ncplot-netcdf-reader"),
     ("plot-renderer", "ncplot-plot-renderer")],
)
def test_each_server_uses_entry_point(
    built_plugin: Path, external_name: str, entry_point: str,
):
    d = json.loads((built_plugin / ".vscode" / "mcp.json").read_text())
    s = d["servers"][external_name]
    assert s["command"] == entry_point
```

- [ ] **Step 4: Other test files** — mirror codex/cursor patterns: test_manifest.py (asserts `plugin.json` at root), test_skills_copied.py, test_mcp_servers_bundled.py, test_commands.py, test_no_hooks.py.

- [ ] **Step 5: Run + commit**

```bash
.venv/bin/pytest tests/targets/copilot -v
git add tests/targets/copilot/
git commit -m "cycle-7 task 12: copilot test suite (incl. servers-vs-mcpServers regression test)"
```

---

## Phase 7: Antigravity target

### Task 13: `targets/antigravity/build.py`

No top-level manifest in Antigravity. Skills land in `.agent/skills/`. Workflows in `.agent/workflows/`. MCP config is a snippet for paste.

**Files:**
- Create: `targets/antigravity/build.py`
- Create: `targets/antigravity/README.md`

- [ ] **Step 1: Write the build.py**

```python
"""Build the Antigravity plugin payload from src/.

Antigravity has no top-level plugin manifest. Skills are discovered
from `.agent/skills/<name>/SKILL.md` (project) or
`~/.gemini/antigravity/skills/<name>/SKILL.md` (global). Workflows
(slash commands) live at `.agent/workflows/<name>.md`. MCP config is
edited via the Antigravity UI; we ship a snippet for paste.

No hook system as of May 2026 (per cycle-7 research).
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import common_ncplot_block
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


PLUGIN_NAME = "ncplot-agent"


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # Skills go under .agent/skills/<name>/SKILL.md
    agent_dir = plugin_dir / ".agent"
    agent_dir.mkdir()
    copy_skills(src_root, agent_dir / "skills")

    # Workflows are .md files at .agent/workflows/<name>.md (slash command target)
    workflows_dir = agent_dir / "workflows"
    workflows_dir.mkdir()
    (workflows_dir / "refine.md").write_text(_refine_workflow())

    # MCP servers — bundled at top level so users can pip install
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # MCP config snippet for paste into Antigravity's mcp_config.json
    mcp_snippet = {
        "mcpServers": {
            s["external_name"]: {
                "command": s["entry_point"],
                "args": [],
            }
            for s in MCP_SERVERS
        }
    }
    (plugin_dir / "mcp_config.json").write_text(
        json.dumps(mcp_snippet, indent=2) + "\n")

    # ncplot metadata for cross-target audit (Antigravity ignores this file)
    (plugin_dir / ".ncplot.json").write_text(
        json.dumps(common_ncplot_block(build_cycle=7), indent=2) + "\n")

    (plugin_dir / "README.md").write_text(_plugin_readme())


def _refine_workflow() -> str:
    return (
        "---\n"
        "description: Review the current session and propose refinement drafts. "
        "(Placeholder — cycle 6 implementation; manual trigger only on Antigravity.)\n"
        "---\n\n"
        "# /refine workflow\n\n"
        "This is a placeholder for the cycle-6 skill-refiner. Once cycle 6 ships, "
        "invoking `/refine` here will run the skill-refiner skill against the "
        "current session's `.ncplot/task-log.jsonl` and produce refinement "
        "drafts under `.ncplot/refinements/` for human review.\n\n"
        "Until then, the task-log is being written but no automatic refinement "
        "happens. Antigravity has no formal hook system as of May 2026, so this "
        "manual workflow trigger is the only path on this host.\n"
    )


def _plugin_readme() -> str:
    return (
        "# ncplot-agent — Antigravity plugin\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Copy `.agent/` into your project\n\n"
        "```bash\n"
        "cp -r .agent /path/to/your/project/\n"
        "```\n\n"
        "Or for global use, copy `.agent/skills/` into "
        "`~/.gemini/antigravity/skills/` and the workflow into the global "
        "workflows dir.\n\n"
        "### 3. Paste mcp_config.json into Antigravity's MCP config\n\n"
        "Open Agent Panel → MCP Servers → \"View raw config\". Merge the "
        "contents of `mcp_config.json` into the displayed JSON.\n\n"
        "### 4. Restart Antigravity\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **No formal hook system on Antigravity.** Cycle-6 self-improvement "
        "Stop hook → manual `/refine` workflow invocation.\n"
        "- **Custom slash commands implemented as workflows** (markdown files in "
        "`.agent/workflows/`). The /refine workflow is a placeholder.\n"
    )
```

- [ ] **Step 2: Smoke test**

```bash
.venv/bin/python -m tools.build antigravity
ls -la build/antigravity/ncplot-agent/
ls build/antigravity/ncplot-agent/.agent/
```

Expected: `.agent/skills/`, `.agent/workflows/refine.md`, `mcp-servers/`, `mcp_config.json`, `README.md`.

- [ ] **Step 3: Commit**

```bash
git add targets/antigravity/build.py
git commit -m "cycle-7 task 13: antigravity build.py — .agent/skills + workflow + mcp_config snippet"
```

---

### Task 14: `tests/targets/antigravity/`

Antigravity has no top-level manifest, so the test suite differs from the others. Replace `test_manifest.py` with `test_no_manifest.py` and add `test_workflow.py`.

- [ ] **Step 1: conftest.py + test_build_runs.py + test_skills_copied.py + test_mcp_servers_bundled.py + test_no_hooks.py** — mirror previous targets, paths swapped to antigravity.

For test_skills_copied.py: skills are at `.agent/skills/` (not at top-level `skills/`). Adjust accordingly:

```python
# tests/targets/antigravity/test_skills_copied.py
from pathlib import Path
import pytest

_EXPECTED = {
    "netcdf-inspect", "netcdf-plot-router",
    "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
}

def test_skills_under_agent_dir(built_plugin: Path):
    skills = built_plugin / ".agent" / "skills"
    assert skills.is_dir()

def test_all_expected_skills(built_plugin: Path):
    actual = {p.name for p in (built_plugin / ".agent" / "skills").iterdir() if p.is_dir()}
    assert actual == _EXPECTED

def test_no_skill_refiner(built_plugin: Path):
    assert not (built_plugin / ".agent" / "skills" / "skill-refiner").exists()

@pytest.mark.parametrize("skill", sorted(_EXPECTED))
def test_skill_md_present(built_plugin: Path, skill: str):
    assert (built_plugin / ".agent" / "skills" / skill / "SKILL.md").is_file()
```

- [ ] **Step 2: test_no_manifest.py**

```python
from pathlib import Path

def test_no_top_level_manifest(built_plugin: Path):
    """Antigravity has no top-level plugin manifest."""
    for f in ("plugin.json", ".claude-plugin", ".codex-plugin",
               ".cursor-plugin", "gemini-extension.json"):
        assert not (built_plugin / f).exists(), (
            f"unexpected manifest: {f}")

def test_ncplot_metadata_file_present(built_plugin: Path):
    """Build still writes a hidden cross-target audit file."""
    assert (built_plugin / ".ncplot.json").is_file()
```

- [ ] **Step 3: test_workflow.py**

```python
from pathlib import Path

def test_refine_workflow_present(built_plugin: Path):
    assert (built_plugin / ".agent" / "workflows" / "refine.md").is_file()

def test_refine_has_frontmatter(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert text.startswith("---\n")

def test_refine_announces_placeholder(built_plugin: Path):
    text = (built_plugin / ".agent" / "workflows" / "refine.md").read_text()
    assert "placeholder" in text.lower() or "cycle 6" in text.lower()
```

- [ ] **Step 4: test_mcp_config_snippet.py**

```python
import json
from pathlib import Path

def test_snippet_parses(built_plugin: Path):
    json.loads((built_plugin / "mcp_config.json").read_text())

def test_uses_mcpServers_key(built_plugin: Path):
    d = json.loads((built_plugin / "mcp_config.json").read_text())
    assert "mcpServers" in d  # Antigravity uses mcpServers (same as Claude Desktop)
    for name in ("netcdf-reader", "plot-renderer"):
        assert name in d["mcpServers"]
```

- [ ] **Step 5: Run + commit**

```bash
.venv/bin/pytest tests/targets/antigravity -v
git add tests/targets/antigravity/
git commit -m "cycle-7 task 14: antigravity test suite (workflow + no-manifest + mcp snippet)"
```

---

## Phase 8: Claude Desktop polish

### Task 15: Refactor `targets/claude-desktop/build.py`

The existing stub concatenates skill bodies into a project-instructions doc (correct approach since Claude Desktop has no native skill loader). Cycle-7 polish:
- Use shared helpers
- Bundle MCP servers with re-rooted source (so users can pip install entry-point scripts)
- Update MCP config snippet to use entry-point commands instead of file paths
- Add a test suite

**Files:**
- Modify: `targets/claude-desktop/build.py`

- [ ] **Step 1: Read the existing build.py to understand current shape**

```bash
cat targets/claude-desktop/build.py
```

(Previously a stub; we'll rewrite.)

- [ ] **Step 2: Write the new build.py**

```python
"""Build the Claude Desktop bundle from src/.

Claude Desktop has no native skill loader, so we concatenate skill
bodies into `project_instructions.md` — the user pastes this into
their Claude Project's instructions panel.

MCP servers ARE supported (stdio, configured via
`claude_desktop_config.json`). Cycle-7 polish: bundle the servers
with re-rooted source + patched pyproject (so users can `pip install`)
and emit an entry-point-based config snippet.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import common_ncplot_block
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import INCLUDED_SKILLS


PLUGIN_NAME = "ncplot-agent"


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # Concatenate skill bodies into project_instructions.md
    pi = ["# ncplot-agent — Claude Desktop project instructions\n",
          "Paste this content into your Claude Project's Custom Instructions "
          "or Project Knowledge.\n",
          "\n---\n"]
    skills_src = src_root / "skills"
    for name in sorted(INCLUDED_SKILLS):
        skill_md = skills_src / name / "SKILL.md"
        if not skill_md.exists():
            raise RuntimeError(f"missing skill: {skill_md}")
        text = skill_md.read_text()
        # Strip YAML frontmatter
        if text.startswith("---\n"):
            end = text.find("\n---\n", 4)
            if end > 0:
                text = text[end + 5:]
        pi.append(f"\n## Skill: {name}\n")
        pi.append(text.strip() + "\n")
        pi.append("\n---\n")
    (plugin_dir / "project_instructions.md").write_text("".join(pi))

    # Bundle MCP servers
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # MCP config snippet (paste into ~/Library/Application Support/Claude/claude_desktop_config.json)
    snippet = {
        "mcpServers": {
            s["external_name"]: {
                "command": s["entry_point"],
                "args": [],
            }
            for s in MCP_SERVERS
        }
    }
    (plugin_dir / "claude_desktop_config_snippet.json").write_text(
        json.dumps(snippet, indent=2) + "\n")

    # Audit metadata
    (plugin_dir / ".ncplot.json").write_text(
        json.dumps(common_ncplot_block(build_cycle=7), indent=2) + "\n")

    (plugin_dir / "README.md").write_text(_readme())


def _readme() -> str:
    return (
        "# ncplot-agent — Claude Desktop bundle\n\n"
        "NetCDF plotting via natural language.\n\n"
        "Claude Desktop has no native skill loader, so this bundle gives you:\n"
        "1. A pre-concatenated `project_instructions.md` to paste into your "
        "Claude Project.\n"
        "2. Two installable MCP servers (`mcp-servers/`).\n"
        "3. A config snippet for `claude_desktop_config.json`.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Merge the config snippet\n\n"
        "On macOS:\n\n"
        "```bash\n"
        "# View existing config\n"
        "cat ~/Library/Application\\ Support/Claude/claude_desktop_config.json\n"
        "```\n\n"
        "Merge `claude_desktop_config_snippet.json` into that file's "
        "`mcpServers` block. Restart Claude Desktop.\n\n"
        "### 3. Paste project_instructions.md into your Claude Project\n\n"
        "Open the project, click the project title to access settings, paste "
        "the contents of `project_instructions.md` into the Custom "
        "Instructions area.\n\n"
        "## Known limitations\n\n"
        "- **No skill loader** → instructions are a single context dump rather "
        "than dynamic skill activation.\n"
        "- **No slash commands.**\n"
        "- **No hooks** → cycle-6 self-improvement is manual only.\n"
    )
```

- [ ] **Step 3: Smoke test**

```bash
.venv/bin/python -m tools.build claude-desktop
ls build/claude-desktop/ncplot-agent/
head -30 build/claude-desktop/ncplot-agent/project_instructions.md
```

- [ ] **Step 4: Commit**

```bash
git add targets/claude-desktop/build.py
git commit -m "cycle-7 task 15: claude-desktop build.py polished — bundled MCP servers + entry-point launch"
```

---

### Task 16: `tests/targets/claude_desktop/`

Test the unique aspects: concatenated instructions, MCP snippet, no top-level manifest.

- [ ] **Step 1: conftest.py** — same pattern, paths swapped.

- [ ] **Step 2: test_build_runs.py + test_concatenated_skills.py + test_mcp_snippet.py + test_mcp_servers_bundled.py**

`test_concatenated_skills.py`:
```python
from pathlib import Path

def test_project_instructions_present(built_plugin: Path):
    assert (built_plugin / "project_instructions.md").is_file()

def test_concatenates_all_5_skills(built_plugin: Path):
    text = (built_plugin / "project_instructions.md").read_text()
    for name in ("netcdf-inspect", "netcdf-plot-router",
                  "netcdf-plot-map", "netcdf-plot-timeseries",
                  "netcdf-plot-profile"):
        assert f"## Skill: {name}" in text, f"missing skill section for {name}"

def test_skill_refiner_excluded(built_plugin: Path):
    text = (built_plugin / "project_instructions.md").read_text()
    assert "## Skill: skill-refiner" not in text

def test_yaml_frontmatter_stripped(built_plugin: Path):
    """Concatenated bodies should not have raw YAML frontmatter blocks."""
    text = (built_plugin / "project_instructions.md").read_text()
    # The doc starts with markdown header, not "---\nname:". Search for any
    # appearances of "name: netcdf-" that would indicate unstripped FM.
    assert "name: netcdf-inspect\n" not in text
```

`test_mcp_snippet.py`:
```python
import json
from pathlib import Path
import pytest

def test_snippet_parses(built_plugin: Path):
    json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())

def test_uses_mcpServers_key(built_plugin: Path):
    d = json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())
    assert "mcpServers" in d

@pytest.mark.parametrize("name,entry", [
    ("netcdf-reader", "ncplot-netcdf-reader"),
    ("plot-renderer", "ncplot-plot-renderer"),
])
def test_each_uses_entry_point(built_plugin: Path, name: str, entry: str):
    d = json.loads((built_plugin / "claude_desktop_config_snippet.json").read_text())
    assert d["mcpServers"][name]["command"] == entry
```

`test_mcp_servers_bundled.py`: copy from cursor/codex tests.

`test_build_runs.py`:
```python
from pathlib import Path

def test_root_present(built_plugin: Path):
    assert built_plugin.is_dir()

def test_no_top_level_manifest(built_plugin: Path):
    """Claude Desktop bundle has no plugin manifest."""
    for f in ("plugin.json", ".claude-plugin", ".cursor-plugin",
               "gemini-extension.json"):
        assert not (built_plugin / f).exists()

def test_required_files(built_plugin: Path):
    for f in ("project_instructions.md",
               "claude_desktop_config_snippet.json", "README.md",
               ".ncplot.json"):
        assert (built_plugin / f).is_file()
```

- [ ] **Step 3: Run + commit**

```bash
.venv/bin/pytest tests/targets/claude_desktop -v
git add tests/targets/claude_desktop/
git commit -m "cycle-7 task 16: claude-desktop test suite (concat skills + MCP snippet + no manifest)"
```

---

## Phase 9: Cross-target + final

### Task 17: `tests/targets/test_all_targets_buildable.py`

**Files:**
- Create: `tests/targets/test_all_targets_buildable.py`

- [ ] **Step 1: Write the test**

```python
"""Smoke test: tools/build.py --all builds every target without conflict."""
from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
TARGETS_ROOT = REPO_ROOT / "targets"
SRC_ROOT = REPO_ROOT / "src"


def _list_targets() -> list[str]:
    """Discover targets the same way tools/build.py does."""
    out = []
    for p in TARGETS_ROOT.iterdir():
        if p.is_dir() and not p.name.startswith("_") and (p / "build.py").exists():
            out.append(p.name)
    return sorted(out)


def _load_build(target: str):
    spec = importlib.util.spec_from_file_location(
        f"targets.{target.replace('-', '_')}.build",
        TARGETS_ROOT / target / "build.py",
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.mark.parametrize("target", _list_targets())
def test_target_builds_to_unique_dir(tmp_path, target: str):
    """Each target writes to <tmp>/<target>/ — never overlapping."""
    if target == "hermes":
        pytest.skip("hermes target stub unverified by cycle-7 research")
    out = tmp_path / target
    out.mkdir()
    mod = _load_build(target)
    if not hasattr(mod, "build"):
        pytest.skip(f"target {target} has no build()")
    mod.build(SRC_ROOT, out)
    plugin_root = out / "ncplot-agent"
    assert plugin_root.is_dir(), f"{target}: missing ncplot-agent dir"
    # Each target produces *something* — at least skills or a manifest
    has_content = any((plugin_root / sub).exists() for sub in
                       ("skills", "mcp-servers", ".agent",
                        "project_instructions.md", "plugin.json",
                        ".claude-plugin", ".codex-plugin", ".cursor-plugin",
                        "gemini-extension.json", ".vscode"))
    assert has_content, f"{target}: empty build artifact"
```

- [ ] **Step 2: Run**

```bash
.venv/bin/pytest tests/targets/test_all_targets_buildable.py -v
```

Expected: 7 cycle-7 targets pass; hermes skipped.

- [ ] **Step 3: Commit**

```bash
git add tests/targets/test_all_targets_buildable.py
git commit -m "cycle-7 task 17: cross-target build smoke test"
```

---

### Task 18: Update `docs/adding-targets.md`

**Files:**
- Modify: `docs/adding-targets.md`

- [ ] **Step 1: Replace the file**

```markdown
# Adding a new target

A target is a build adapter that turns the canonical `src/` content into
a plugin format consumable by a specific agent host.

## Standard target template

After cycle 7, every target uses shared helpers from
`targets/_common/`. The skeleton:

```python
# targets/<host>/build.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION,
    PLUGIN_HOMEPAGE, PLUGIN_LICENSE, PLUGIN_AUTHOR,
    common_ncplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # 1. Manifest (host-specific path + shape)
    # 2. copy_skills(src_root, plugin_dir / "skills")
    # 3. bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")
    # 4. Host-specific MCP launch config (path + key name varies)
    # 5. Slash command (md / TOML / native)
    # 6. README
```

## Host-specific config files

| Host | MCP config path | MCP config key | Manifest path |
|------|-----------------|----------------|---------------|
| Claude Code | `.mcp.json` | `mcpServers` | `.claude-plugin/plugin.json` |
| Codex | `config.toml` (TOML) | `[mcp_servers.X]` | `.codex-plugin/plugin.json` |
| Gemini CLI | `settings.json` | `mcpServers` | `gemini-extension.json` (root) |
| Cursor | `.cursor/mcp.json` | `mcpServers` | `.cursor-plugin/plugin.json` |
| GitHub Copilot | `.vscode/mcp.json` | `servers` ⚠ | `plugin.json` (root) |
| Antigravity | `mcp_config.json` (snippet) | `mcpServers` | n/a (no manifest) |
| Claude Desktop | `claude_desktop_config_snippet.json` | `mcpServers` | n/a (project doc) |

## Host-specific gotchas

- **Copilot uses `servers`, not `mcpServers`.** The only host with
  this naming. A regression test (`tests/targets/copilot/test_servers_key.py`)
  guards against accidental cross-target contamination.
- **Antigravity has no formal hook system.** Cycle-6 self-improvement
  degrades to a manual `/refine` workflow.
- **Claude Desktop has no skill loader.** Skills are concatenated into
  a project-instructions document. YAML frontmatter is stripped.
- **Codex slash-command authoring is undocumented.** We omit a
  `/refine` command on Codex pending a confirmed format.

## Test suite template

Each target gets `tests/targets/<host_underscore>/`:
- `conftest.py` — module-scoped `built_plugin` fixture
- `test_build_runs.py` — top-level structure
- `test_manifest.py` (or analog) — manifest shape
- `test_skills_copied.py` — allowlist + skill-refiner exclusion
- `test_mcp_servers_bundled.py` — re-rooted source + patched pyproject
- `test_<host>_mcp.py` — host-specific MCP config validation
- `test_commands.py` — slash command / workflow file
- `test_no_hooks.py` — cycle-6 deferral

## See also

- `docs/architecture.md` — overall L1/L2/L3 layering
- `docs/research/2026-05-08-multi-host-survey.md` — host plugin model
  research
- `targets/claude-code/build.py` — reference implementation
- `targets/_common/` — shared helpers
```

- [ ] **Step 2: Commit**

```bash
git add docs/adding-targets.md
git commit -m "cycle-7 task 18: adding-targets.md updated for cycle-7 reality"
```

---

### Task 19: Final lint + suite + push + PR

- [ ] **Step 1: Lint cycle-7 sources**

```bash
.venv/bin/ruff check targets/ tools/build.py tests/targets
```

Fix violations.

- [ ] **Step 2: mypy**

```bash
.venv/bin/mypy targets/_common targets/codex/build.py targets/gemini-cli/build.py \
                targets/cursor/build.py targets/copilot/build.py \
                targets/antigravity/build.py targets/claude-desktop/build.py 2>&1 | head -30
```

Fix any hard failures.

- [ ] **Step 3: Build all targets via the dispatcher**

```bash
.venv/bin/python -m tools.build --all
ls build/
```

Expected: 6 cycle-7 target dirs (claude-code, claude-desktop, codex, cursor, gemini-cli, copilot, antigravity, hermes — but hermes will fail since stub is unchanged; that's expected and accepted).

- [ ] **Step 4: Validate each target**

```bash
for t in claude-code codex cursor gemini-cli copilot antigravity claude-desktop; do
  .venv/bin/python -m tools.build $t --validate || echo "FAILED: $t"
done
```

- [ ] **Step 5: Run the full repo suite**

```bash
.venv/bin/pytest -v 2>&1 | tail -30
```

- [ ] **Step 6: Commit fixes if any**

```bash
git add -A
git commit -m "cycle-7 final gate: full lint + suite green"
```

- [ ] **Step 7: Push**

```bash
git push -u origin cycle-7-multi-host-targets
```

- [ ] **Step 8: PR**

```bash
gh pr create --base master --head cycle-7-multi-host-targets \
  --title "Cycle 7: multi-host targets (Codex, Gemini CLI, Cursor, Copilot, Antigravity, Claude Desktop polish)" \
  --body "$(cat <<'EOF'
## Summary

Adds 5 new build targets — Codex CLI/Desktop, Gemini CLI, Cursor,
GitHub Copilot, Antigravity — and polishes Claude Desktop. Each target
produces an installable plugin payload tailored to that host's plugin
format.

Reuses cycle-4 build pattern via shared helpers in `targets/_common/`:
- `skills.py` — allowlist + copy helper
- `mcp_bundling.py` — re-rooted MCP server bundling
- `manifest.py` — shared metadata constants

Each per-target `build.py` is ~50–100 LOC of host-specific glue.

## Stats

- 19 plan tasks across 9 phases
- 5 new target builders + 1 polish + 1 refactor
- ~40 new tests under `tests/targets/<host>/`
- Updated `docs/architecture.md` + `docs/adding-targets.md`
- Saved multi-host research at `docs/research/2026-05-08-multi-host-survey.md`

## What's NOT in this PR

- Skill-refiner skill + Stop hooks (cycle 6)
- Auto-installer for cartopy/scipy (cycle 5)
- Hermes target validation
- Marketplace publishing for any host
- Codex custom slash-command (Codex format undocumented)

## Test plan

- [ ] `pytest -v` (full suite green)
- [ ] `python -m tools.build --all` (every target builds without error)
- [ ] `python -m tools.build <target> --validate` for each (per-target suite passes)
- [ ] **Manual:** install the Codex bundle into a Codex CLI session;
  exercise the netcdf-plot-map skill end-to-end

## References

- Spec: `docs/specs/2026-05-08-cycle-7-multi-host-targets.md`
- Plan: `docs/plans/2026-05-08-cycle-7-multi-host-targets.md`
- Research: `docs/research/2026-05-08-multi-host-survey.md`
EOF
)"
```

- [ ] **Step 9: Capture PR URL.**

---

## End of plan

19 tasks, 9 phases:

| Phase | Tasks | Theme |
|-------|-------|-------|
| 1 | 1–3 | Shared helpers (`targets/_common/`) |
| 2 | 4 | Refactor Claude Code to use helpers |
| 3 | 5–6 | Codex CLI/Desktop target |
| 4 | 7–8 | Gemini CLI target |
| 5 | 9–10 | Cursor target |
| 6 | 11–12 | GitHub Copilot target |
| 7 | 13–14 | Antigravity target |
| 8 | 15–16 | Claude Desktop polish |
| 9 | 17–19 | Cross-target test + docs update + push + PR |

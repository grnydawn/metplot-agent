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

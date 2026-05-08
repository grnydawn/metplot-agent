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

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_KEYWORDS, PLUGIN_AUTHOR,
    common_metplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.setup_descriptions import SETUP_COMMAND_DESCRIPTION
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
        "metplot": common_metplot_block(build_cycle=7),
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

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # /setup slash command (Codex uses bare names; no namespace prefix)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir(exist_ok=True)
    # user-invocable: true frontmatter mirrors the skill convention; effect on
    # commands/*.md not empirically verified for this host (cycle-6 follow-up).
    (commands_dir / "setup.md").write_text(
        "---\n"
        "description: " + SETUP_COMMAND_DESCRIPTION + "\n"
        "user-invocable: true\n"
        "---\n\n"
        "Run the bundled `setup.sh` to install or refresh the dependency stack.\n"
    )

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
        "# metplot — Codex plugin\n\n"
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
        "(typically `~/.codex/plugins/metplot/`), or follow the "
        "Codex marketplace install flow if available.\n\n"
        "### 3. Merge config.toml into your Codex config\n\n"
        "Append the contents of `config.toml` to `~/.codex/config.toml` "
        "(or your project-scoped `.codex/config.toml`).\n\n"
        "### 4. Restart Codex CLI / Desktop\n\n"
        "## Setup\n\n"
        "Run the bundled installer to install Python dependencies:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
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

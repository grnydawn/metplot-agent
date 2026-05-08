"""Build the Gemini CLI extension from src/.

Gemini CLI loads `gemini-extension.json` at the root of an extension,
discovers `skills/` natively, reads MCP servers from `settings.json`,
and runs slash commands from `commands/<name>.toml`.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
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

    # gemini-extension.json (root manifest)
    extension_manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "homepage": PLUGIN_HOMEPAGE,
        "skills": "skills",
        "commands": "commands",
        "metplot": common_metplot_block(build_cycle=7),
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

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # commands/metplot/ subdir — subdir name → colon namespace (/metplot:setup, /metplot:refine)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    metplot_cmd_dir = commands_dir / "metplot"
    metplot_cmd_dir.mkdir()
    (metplot_cmd_dir / "refine.toml").write_text(_refine_toml())
    (metplot_cmd_dir / "setup.toml").write_text(
        'description = "' + SETUP_COMMAND_DESCRIPTION + '"\n'
        'prompt = "Run the bundled setup.sh to install metplot\'s Python dependencies."\n'
    )

    # Plugin README
    (plugin_dir / "README.md").write_text(_plugin_readme())


def _refine_toml() -> str:
    return (
        'description = "Review the current session and propose refinement '
        'drafts to the canonical skills. (Placeholder — full implementation '
        'in cycle 6.)"\n'
        'prompt = "The /refine command is a placeholder until cycle 6 ships '
        'the skill-refiner skill. Until then: skills are appending corrections '
        'to .metplot/task-log.jsonl, but no automatic refinement happens."\n'
    )


def _plugin_readme() -> str:
    skills = sorted([
        "netcdf-inspect", "netcdf-plot-router",
        "netcdf-plot-map", "netcdf-plot-timeseries", "netcdf-plot-profile",
    ])
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    return (
        "# metplot — Gemini CLI extension\n\n"
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
        "Or copy this directory to `~/.gemini/extensions/metplot/`.\n\n"
        "### 3. Merge settings.json into your Gemini settings\n\n"
        "The MCP launch stanzas need to land in `~/.gemini/settings.json` "
        "(global) or `.gemini/settings.json` (project). Use a JSON merge "
        "tool or copy the `mcpServers` block into your existing settings.\n\n"
        "### 4. Restart Gemini CLI\n\n"
        "## Setup\n\n"
        "Run the bundled installer to install Python dependencies:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
        "## What's inside\n\nSkills:\n" + skill_lines + "\n\n"
        "Slash commands:\n  - `/refine` — placeholder (cycle 6)\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Gemini's `SessionEnd` hook will "
        "trigger the skill-refiner once it ships.\n"
    )

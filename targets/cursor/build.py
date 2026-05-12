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

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_AUTHOR,
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

    manifest_dir = plugin_dir / ".cursor-plugin"
    manifest_dir.mkdir()
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "metplot": common_metplot_block(build_cycle=7),
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

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # commands/ — refine + /setup (Cursor doesn't namespace; bare command)
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(_refine_md())
    (commands_dir / "setup.md").write_text(
        "---\n"
        "description: " + SETUP_COMMAND_DESCRIPTION + "\n"
        "---\n\n"
        "Run the bundled `setup.sh` from the plugin root.\n"
    )

    (plugin_dir / "README.md").write_text(_plugin_readme())


def _refine_md() -> str:
    return (
        "---\n"
        "description: Propose refinement drafts to the canonical metplot "
        "skills based on the current session.\n"
        "---\n\n"
        "Invoke the `skill-refiner` skill against this session.\n\n"
        "Read `.metplot/task-log.jsonl` plus the current conversation. "
        "Tag observations using the refiner's six categories (`alias`, "
        "`region`, `pitfall`, `user_pref`, `default`, `failure_mode`). "
        "Write each draft to "
        "`.metplot/refinements/<timestamp>-<target>-<tag>.md` with YAML "
        "frontmatter naming the target file, section, operation, "
        "confidence, and evidence.\n\n"
        "Cursor has no Stop-hook equivalent, so `/refine` is "
        "manual-trigger only on this host. Do not modify canonical "
        "skill files directly; the user applies drafts with "
        "`metplot-refine`.\n"
    )


def _plugin_readme() -> str:
    return (
        "# metplot — Cursor plugin\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "Copy this directory to `~/.cursor/plugins/metplot/`, "
        "or use the Cursor Marketplace install flow.\n\n"
        "### 3. Restart Cursor\n\n"
        "## Setup\n\n"
        "Run the bundled installer to install Python dependencies:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Cursor's `stop` hook (camelCase) "
        "will trigger skill-refiner once it ships.\n"
    )

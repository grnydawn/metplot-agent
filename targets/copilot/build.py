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
        "# ncplot — GitHub Copilot agent plugin\n\n"
        "NetCDF plotting via natural language.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "From VS Code: Chat → Install Plugin From Source → select this directory.\n\n"
        "Or copy to `~/.copilot/plugins/ncplot/`.\n\n"
        "### 3. Restart VS Code\n\n"
        "## Known limitations (cycle 7)\n\n"
        "- **Hooks deferred to cycle 6.** Copilot's `Stop` hook (PascalCase) "
        "will trigger skill-refiner once it ships.\n"
        "- **Plugin system in Preview.** Some rough edges expected as of "
        "May 2026.\n"
    )

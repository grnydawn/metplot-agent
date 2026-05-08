"""Build the Claude Code plugin from src/.

Cycle 4 baseline: produces a payload at `build/claude-code/ncplot/`
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


def _plugin_readme(included_skills=None) -> str:
    # Legacy stub kept for internal call; _plugin_readme_full is used instead
    return ""


def _plugin_readme_full(skills: list[str], mcps: list[str]) -> str:
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps)
    mcp_install = "\n".join(
        f"pip install ./mcp-servers/{s['package_dir']}"
        for s in MCP_SERVERS
    )
    return (
        "# ncplot — Claude Code plugin\n\n"
        "NetCDF plotting via natural language. Maps, time series, and "
        "vertical profiles. WRF/ROMS/CMIP/reanalysis aware.\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n" + mcp_install + "\n```\n\n"
        "### 2. Install the plugin\n\n"
        "```bash\ncp -r . ~/.claude/plugins/ncplot\n```\n\n"
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

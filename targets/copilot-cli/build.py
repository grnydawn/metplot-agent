"""Build the standalone GitHub Copilot CLI plugin from src/.

This target is for the **standalone GitHub Copilot CLI** (the terminal
coding agent), kept deliberately distinct from `targets/copilot/` (the
VS Code Copilot plugin). The whole reason for a separate target is the
**MCP config surface**:

- The VS Code plugin writes `.vscode/mcp.json` keyed on `servers`.
- The standalone CLI reads `~/.copilot/mcp-config.json` keyed on
  `mcpServers`, with per-server `type: "local"` entries (stdio launch).

So this build emits a CLI-format `mcp-config.json` (key `mcpServers`,
`type:"local"`, `args:[]`, `tools:["*"]`) instead of `.vscode/mcp.json`.
Everything else — skills, re-rooted MCP server packages, install
tooling, manifest — reuses the shared `_common` helpers, identical to
the VS Code target.

> Stale note corrected: `docs/research/2026-05-08-multi-host-survey.md`
> previously implied the standalone CLI reuses the VS Code plugin/MCP
> format. The CLI's MCP surface (`~/.copilot/mcp-config.json` /
> `mcpServers` / `type:"local"`) is distinct; see the issue AC16.
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

    # plugin.json at root (Copilot convention; not under a .copilot-plugin dir)
    manifest = {
        "name": PLUGIN_NAME,
        "version": PLUGIN_VERSION,
        "description": PLUGIN_DESCRIPTION,
        "author": PLUGIN_AUTHOR,
        "homepage": PLUGIN_HOMEPAGE,
        "license": PLUGIN_LICENSE,
        "metplot": common_metplot_block(build_cycle=7),
    }
    (plugin_dir / "plugin.json").write_text(
        json.dumps(manifest, indent=2) + "\n")

    copy_skills(src_root, plugin_dir / "skills")
    bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")

    # mcp-config.json — the distinguishing surface vs the VS Code plugin.
    # The standalone Copilot CLI reads ~/.copilot/mcp-config.json keyed on
    # `mcpServers` (NOT `servers`), with per-server `type: "local"` stdio
    # entries. This file is what the user merges into ~/.copilot/mcp-config.json.
    mcp_servers = {
        s["external_name"]: {
            "type": "local",
            "command": s["entry_point"],
            "args": [],
            "tools": ["*"],
        }
        for s in MCP_SERVERS
    }
    (plugin_dir / "mcp-config.json").write_text(
        json.dumps({"mcpServers": mcp_servers}, indent=2) + "\n")

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # commands/ — refine + /metplot:setup. The standalone CLI exposes no
    # documented Stop-hook surface (same as the VS Code plugin), so
    # `/refine` is manual-trigger only on this host.
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(
        "---\n"
        "description: Propose refinement drafts to the canonical metplot "
        "skills based on the current session.\n"
        "user-invocable: true\n"
        "---\n\n"
        "Invoke the `skill-refiner` skill against this session.\n\n"
        "Read `.metplot/task-log.jsonl` plus the current conversation. "
        "Tag observations using the refiner's six categories (`alias`, "
        "`region`, `pitfall`, `user_pref`, `default`, `failure_mode`). "
        "Write each draft to "
        "`.metplot/refinements/<timestamp>-<target>-<tag>.md` with YAML "
        "frontmatter naming the target file, section, operation, "
        "confidence, and evidence.\n\n"
        "The standalone Copilot CLI exposes no Stop-hook surface, so "
        "`/refine` is manual-trigger only on this host. Do not modify "
        "canonical skill files directly; the user applies drafts with "
        "`metplot-refine`.\n"
    )
    (commands_dir / "setup.md").write_text(
        "---\n"
        "description: " + SETUP_COMMAND_DESCRIPTION + "\n"
        "user-invocable: true\n"
        "---\n\n"
        "Run the bundled `setup.sh` from the plugin root.\n"
    )

    (plugin_dir / "README.md").write_text(_plugin_readme())


def _plugin_readme() -> str:
    return (
        "# metplot — GitHub Copilot CLI plugin\n\n"
        "NetCDF plotting via natural language, for the **standalone "
        "GitHub Copilot CLI** (terminal coding agent).\n\n"
        "## Install\n\n"
        "### 1. Install the MCP servers\n\n"
        "```bash\n"
        "pip install ./mcp-servers/netcdf_reader\n"
        "pip install ./mcp-servers/plot_renderer\n"
        "```\n\n"
        "### 2. Register the MCP servers with the CLI\n\n"
        "Merge the bundled `mcp-config.json` into "
        "`~/.copilot/mcp-config.json`. It uses the `mcpServers` key with "
        "`type: \"local\"` stdio entries — distinct from the VS Code "
        "plugin's `.vscode/mcp.json` (`servers` key).\n\n"
        "### 3. Enable the skills\n\n"
        "The CLI auto-reads skills from `.claude/skills/` and "
        "`.agents/skills/`. Point it at the bundled `skills/` tree (copy "
        "to `~/.copilot/skills/metplot/` or a project `.agents/skills/`).\n\n"
        "## Setup\n\n"
        "Run the bundled installer to install Python dependencies:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
        "## Known limitations\n\n"
        "- **No Stop hook wiring.** The standalone Copilot CLI exposes no "
        "documented Stop-hook surface as of June 2026, so the "
        "`skill-refiner` skill is manual-trigger only via `/refine` on "
        "this host.\n"
        "- **Plugin system in Preview.** Some rough edges expected.\n"
    )

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

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import PLUGIN_NAME, common_ncplot_block
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


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

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # /setup workflow
    (workflows_dir / "setup.md").write_text(
        "---\n"
        "description: Install or repair ncplot's Python dependencies. Idempotent.\n"
        "---\n\n"
        "# /setup workflow\n\n"
        "Run the bundled `setup.sh` from the plugin root. Idempotent — safe to "
        "re-run after dependency changes.\n"
    )

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
        "# ncplot — Antigravity plugin\n\n"
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

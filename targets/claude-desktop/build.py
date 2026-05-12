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

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import PLUGIN_NAME, common_metplot_block
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import INCLUDED_SKILLS


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # Concatenate skill bodies into project_instructions.md
    pi = ["# metplot — Claude Desktop project instructions\n",
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

    # Cycle-5 setup tooling (no slash command — Claude Desktop has no slash system)
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

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
    (plugin_dir / ".metplot.json").write_text(
        json.dumps(common_metplot_block(build_cycle=7), indent=2) + "\n")

    (plugin_dir / "README.md").write_text(_readme())


def _readme() -> str:
    return (
        "# metplot — Claude Desktop bundle\n\n"
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
        "## Setup\n\n"
        "Run the bundled installer to install Python dependencies:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
        "## Known limitations\n\n"
        "- **No skill loader** → instructions are a single context dump rather "
        "than dynamic skill activation. `skill-refiner` ships concatenated "
        "into `project_instructions.md`; invoke it manually by asking the "
        "model to \"run the skill-refiner procedure for this session\" at "
        "end of session.\n"
        "- **No slash commands.**\n"
        "- **No hooks** → the refiner is manual-trigger only on this host.\n"
    )

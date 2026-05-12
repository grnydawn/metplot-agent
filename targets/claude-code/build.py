"""Build the Claude Code plugin from src/.

Cycle 4 baseline: produces a payload at `build/claude-code/metplot/`
with skills, bundled MCP servers, .mcp.json, and a placeholder /refine
command.

Cycle 7: refactored to use targets/_common helpers. Behavior identical.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.install_tooling import copy_install_tooling
from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION, PLUGIN_HOMEPAGE,
    PLUGIN_LICENSE, PLUGIN_KEYWORDS, PLUGIN_AUTHOR,
    common_metplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills


MARKETPLACE_NAME = "metplot-local"


def build(src_root: Path, out_root: Path) -> None:
    """Build the Claude Code plugin into `out_root/<PLUGIN_NAME>/`.

    Also emits `out_root/.claude-plugin/marketplace.json` so users can
    register the build directory as a Claude Code plugin marketplace
    via `/plugin marketplace add <out_root>` and install with
    `/plugin install <PLUGIN_NAME>@<MARKETPLACE_NAME>`.
    """
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    marketplace_dir = out_root / ".claude-plugin"
    if marketplace_dir.exists():
        shutil.rmtree(marketplace_dir)
    marketplace_dir.mkdir(parents=True)

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
        "metplot": common_metplot_block(build_cycle=4),
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

    # Cycle-5 setup tooling
    repo_root = Path(__file__).resolve().parents[2]
    copy_install_tooling(repo_root, plugin_dir)

    # Cycle-6 follow-up: pre-create bin/ so Claude Code auto-adds it to
    # PATH at plugin-load time. setup.sh fills it with launcher shims
    # during SessionStart so .mcp.json's bare command names resolve.
    (plugin_dir / "bin").mkdir(exist_ok=True)

    # SessionStart hook (auto-fire setup on first run / version bump)
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)
    (hooks_dir / "setup.json").write_text(json.dumps({
        "SessionStart": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": "${CLAUDE_PLUGIN_ROOT}/setup.sh --quiet",
            }],
        }],
    }, indent=2) + "\n")

    # Stop hook — spawn a fresh subagent to run /metplot:refine when the
    # parent session finishes. Best-effort: skip cleanly if `claude` is
    # not on PATH; always exit 0 so a refiner hiccup never blocks the
    # parent session end (spec §4 principle 6). The subagent runs in the
    # background via `nohup … &` so the hook returns immediately rather
    # than blocking the parent on the refinement-LLM round-trip.
    (hooks_dir / "refine.json").write_text(json.dumps({
        "Stop": [{
            "matcher": "*",
            "hooks": [{
                "type": "command",
                "command": (
                    "command -v claude >/dev/null 2>&1 && "
                    "(nohup claude -p '/metplot:refine' "
                    ">/dev/null 2>&1 &); exit 0"
                ),
            }],
        }],
    }, indent=2) + "\n")

    # Slash commands
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(_refine_command_md())

    # /metplot:setup slash command
    (commands_dir / "setup.md").write_text(
        "---\n"
        "description: Install or repair metplot's Python dependencies "
        "(MCP servers, cartopy, scipy). Idempotent.\n"
        "---\n\n"
        "Run `${CLAUDE_PLUGIN_ROOT}/setup.sh` to install or refresh the "
        "metplot dependency stack. Pass --no-cartopy or --no-scipy to "
        "opt out of optional packages.\n"
    )

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

    # Marketplace manifest (sibling of the plugin dir). Lets users
    # register `out_root` as a Claude Code plugin marketplace.
    marketplace = {
        "$schema": "https://anthropic.com/claude-code/marketplace.schema.json",
        "name": MARKETPLACE_NAME,
        "description": (
            "Local marketplace for the metplot Claude Code plugin, "
            "produced by `python -m tools.build claude-code`."
        ),
        "owner": PLUGIN_AUTHOR,
        "plugins": [
            {
                "name": PLUGIN_NAME,
                "description": PLUGIN_DESCRIPTION,
                "version": PLUGIN_VERSION,
                "author": PLUGIN_AUTHOR,
                "homepage": PLUGIN_HOMEPAGE,
                "license": PLUGIN_LICENSE,
                "keywords": PLUGIN_KEYWORDS,
                "category": "data-science",
                "source": f"./{PLUGIN_NAME}",
            },
        ],
    }
    (marketplace_dir / "marketplace.json").write_text(
        json.dumps(marketplace, indent=2) + "\n")


def _refine_command_md() -> str:
    return (
        "---\n"
        "description: Propose refinement drafts to the canonical metplot "
        "skills based on the current session.\n"
        "---\n"
        "\n"
        "Invoke the `skill-refiner` skill against this session.\n"
        "\n"
        "Read `.metplot/task-log.jsonl` plus the current conversation. "
        "Tag observations using the refiner's six categories "
        "(`alias`, `region`, `pitfall`, `user_pref`, `default`, "
        "`failure_mode`). Write each draft to "
        "`.metplot/refinements/<timestamp>-<target>-<tag>.md` with YAML "
        "frontmatter naming the target file, section, operation, "
        "confidence, and evidence.\n"
        "\n"
        "Do not modify canonical skill files directly. The user reviews "
        "drafts and applies them out-of-band with `metplot-refine`.\n"
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
        "# metplot — Claude Code plugin\n\n"
        "NetCDF plotting via natural language. Maps, time series, and "
        "vertical profiles. WRF/ROMS/CMIP/reanalysis aware.\n\n"
        "## Install\n\n"
        "This directory's parent (`build/claude-code/`) is a self-contained "
        "Claude Code plugin marketplace. Register it once, then install with "
        "the standard `/plugin` flow.\n\n"
        "### 1. Register the marketplace\n\n"
        "In Claude Code, run:\n\n"
        "```text\n"
        "/plugin marketplace add /absolute/path/to/metplot-agent/build/claude-code\n"
        "```\n\n"
        "### 2. Install the plugin\n\n"
        "```text\n"
        f"/plugin install {PLUGIN_NAME}@{MARKETPLACE_NAME}\n"
        "```\n\n"
        "### 3. Restart Claude Code\n\n"
        "The bundled `SessionStart` hook then auto-runs `setup.sh --quiet`, "
        "which installs the Python dependencies the MCP servers need.\n\n"
        "Verify the install: type `/` in the prompt and check that "
        f"`/{PLUGIN_NAME}:setup` and `/{PLUGIN_NAME}:refine` appear.\n\n"
        "## Setup (manual)\n\n"
        "The `SessionStart` hook handles dependency install automatically, "
        "but if you want to install ahead of time or repair a broken "
        "environment, run the bundled installer directly:\n\n"
        "```bash\n./setup.sh\n```\n\n"
        "On Windows: `./setup.ps1`. Pass `--no-cartopy` or `--no-scipy` to "
        "opt out of optional packages. The script is idempotent.\n\n"
        "If you prefer to install the MCP servers without the cartopy/scipy "
        "stack, do it directly with pip:\n\n"
        "```bash\n" + mcp_install + "\n```\n\n"
        "## What's inside\n\nSkills:\n" + skill_lines + "\n\n"
        "MCP servers:\n" + mcp_lines + "\n\n"
        "Slash commands:\n"
        f"  - `/{PLUGIN_NAME}:setup` — install or repair Python dependencies\n"
        f"  - `/{PLUGIN_NAME}:refine` — placeholder (cycle 6)\n\n"
        "Hooks: SessionStart (auto-fires `setup.sh --quiet`).\n\n"
        "## Build provenance\n\n"
        "Built by `targets/claude-code/build.py` from `src/`. Rebuild with:\n\n"
        "```bash\npython -m tools.build claude-code\n```\n"
    )


# Backwards-compat re-export for tests that imported PLUGIN_NAME directly
__all__ = ["PLUGIN_NAME", "build"]

"""Build the Claude Code plugin from src/.

A Claude Code plugin lives in a directory with this layout:

    plugin-name/
    ├── .claude-plugin/
    │   └── plugin.json         # manifest
    ├── skills/
    │   └── <skill>/SKILL.md    # one per skill, plus references/scripts/
    ├── commands/               # optional slash commands
    ├── agents/                 # optional subagents
    ├── hooks/                  # optional hook scripts
    └── mcp-servers/            # optional bundled MCP servers

This builder copies skills as-is (the SKILL.md format is identical),
emits the manifest, wires in the MCP servers, and installs the
session-end hook for the skill-refiner closed loop.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

PLUGIN_NAME = "ncplot-agent"


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # Manifest
    manifest_dir = plugin_dir / ".claude-plugin"
    manifest_dir.mkdir()
    manifest = {
        "name": PLUGIN_NAME,
        "version": "0.1.0",
        "description": "Natural-language plotting from NetCDF files, with self-improving skills.",
        "author": {"name": "ncplot-agent contributors"},
        "homepage": "https://github.com/your-org/ncplot-agent",
        "license": "MIT",
    }
    (manifest_dir / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")

    # Skills — direct copy
    skills_src = src_root / "skills"
    skills_dst = plugin_dir / "skills"
    skills_dst.mkdir()
    skill_names = []
    for s in sorted(skills_src.iterdir()):
        if not s.is_dir():
            continue
        shutil.copytree(s, skills_dst / s.name)
        skill_names.append(s.name)

    # MCP servers — bundle source and emit launch config
    mcp_dst = plugin_dir / "mcp-servers"
    mcp_dst.mkdir()
    mcp_servers = {}
    for m in sorted((src_root / "mcp").iterdir()):
        if not m.is_dir():
            continue
        shutil.copytree(m, mcp_dst / m.name)
        # MCP entry point: each server has server.py
        entry = mcp_dst / m.name / "server.py"
        if entry.exists():
            mcp_servers[m.name] = {
                "command": "python",
                "args": ["${CLAUDE_PLUGIN_ROOT}/mcp-servers/" + m.name + "/server.py"],
            }

    # Shared data — drop into a known place reachable from skills
    data_src = src_root / "data"
    if data_src.exists():
        shutil.copytree(data_src, plugin_dir / "data")

    # Hooks — wire skill-refiner to fire at session end
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir()
    refiner_hook = hooks_dir / "session_end_refiner.sh"
    refiner_hook.write_text(
        "#!/usr/bin/env bash\n"
        "# Trigger the skill-refiner skill at session end so it can review\n"
        "# the task log and propose refinement drafts.\n"
        "#\n"
        "# Claude Code invokes this with the session transcript on stdin.\n"
        "# The agent itself does the refinement work; this hook just emits\n"
        "# the prompt that loads the skill-refiner skill.\n"
        "echo \"Run the skill-refiner skill on this session's task log if any\"\n"
        "echo \"corrections, surprises, or non-trivial problem solving occurred.\"\n"
    )
    refiner_hook.chmod(0o755)

    # Hook configuration — Claude Code reads hooks from plugin.json or a
    # dedicated hooks/config.json, depending on version. Emit both for safety.
    hook_config = {
        "Stop": [
            {
                "matcher": "*",
                "hooks": [
                    {
                        "type": "command",
                        "command": "${CLAUDE_PLUGIN_ROOT}/hooks/session_end_refiner.sh",
                    }
                ],
            }
        ]
    }
    (hooks_dir / "config.json").write_text(json.dumps(hook_config, indent=2) + "\n")

    # MCP server configuration — Claude Code reads from .mcp.json (project-scoped)
    # or from the plugin manifest. We emit a separate file the user can
    # symlink/include.
    if mcp_servers:
        mcp_cfg = {"mcpServers": mcp_servers}
        (plugin_dir / ".mcp.json").write_text(json.dumps(mcp_cfg, indent=2) + "\n")

    # Slash commands — bundle a /refine command that invokes the refiner manually
    commands_dir = plugin_dir / "commands"
    commands_dir.mkdir()
    (commands_dir / "refine.md").write_text(
        "---\n"
        "description: Review the current session and propose refinement drafts to the canonical skills.\n"
        "---\n"
        "\n"
        "Invoke the `skill-refiner` skill on the current session's task log "
        "and conversation history. Propose draft refinements under "
        "`.ncplot/refinements/` for human review. Do not modify any canonical "
        "skill files directly.\n"
    )

    # Install README
    install_readme = plugin_dir / "README.md"
    install_readme.write_text(_install_readme(skill_names, list(mcp_servers)))


def _install_readme(skills: list[str], mcps: list[str]) -> str:
    skill_lines = "\n".join(f"  - `{s}`" for s in skills)
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps) or "  (none)"
    return f"""# ncplot-agent — Claude Code plugin

NetCDF plotting via natural language, with closed-loop skill refinement.

## Install

From this build artifact directory:

```
# Drop into your Claude Code plugins directory
cp -r . ~/.claude/plugins/ncplot-agent
```

Or, in a project, add to `.claude/settings.json`:

```json
{{
  "plugins": [
    "/absolute/path/to/build/claude-code/ncplot-agent"
  ]
}}
```

## What's inside

Skills:
{skill_lines}

MCP servers:
{mcp_lines}

Hooks:
  - `Stop` → `hooks/session_end_refiner.sh` (runs the skill-refiner)

Slash commands:
  - `/refine` — manual refinement review

## Setup

Install the MCP server dependencies once:

```
pip install xarray netcdf4 cftime numpy matplotlib cartopy mcp
```

Then start Claude Code in a directory with NetCDF files. The plugin is
active automatically.

## Self-improvement loop

After a session with corrections or new patterns, the `Stop` hook nudges
the agent to consider running the `skill-refiner` skill. Drafts land in
`.ncplot/refinements/`. Review and apply them with:

```
ncplot-refine
```

(or `python -m tools.apply_refinements` from this repo).
"""

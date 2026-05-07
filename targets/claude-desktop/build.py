"""Build the Claude Desktop integration from src/.

Claude Desktop doesn't load skills natively — its primary extension surface
is MCP servers (configured in `claude_desktop_config.json`). This builder:

1. Emits an `mcp_config_snippet.json` the user merges into their Desktop config.
2. Concatenates all skill bodies into a single `project_instructions.md` that
   the user attaches to a Project, giving the model the same procedural
   knowledge a real skill loader would inject.
3. Bundles MCP server source so the user can run them locally.

The skill-refiner closed-loop has reduced functionality here: there's no
session-end hook, so refinement is manual via /refine.
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

OUT_NAME = "ncplot-agent-claude-desktop"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def build(src_root: Path, out_root: Path) -> None:
    out_dir = out_root / OUT_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Bundle MCP servers
    mcp_dst = out_dir / "mcp-servers"
    mcp_dst.mkdir()
    mcp_servers: dict[str, dict] = {}
    for m in sorted((src_root / "mcp").iterdir()):
        if not m.is_dir():
            continue
        shutil.copytree(m, mcp_dst / m.name)
        entry = mcp_dst / m.name / "server.py"
        if entry.exists():
            # User needs to substitute INSTALL_PATH after copying.
            mcp_servers[m.name] = {
                "command": "python",
                "args": ["INSTALL_PATH/mcp-servers/" + m.name + "/server.py"],
            }

    # MCP config snippet
    snippet = {"mcpServers": mcp_servers}
    (out_dir / "mcp_config_snippet.json").write_text(
        json.dumps(snippet, indent=2) + "\n"
    )

    # Concatenate skills into project instructions
    instructions = _concat_skills(src_root / "skills")
    (out_dir / "project_instructions.md").write_text(instructions)

    # Copy reference data
    data_src = src_root / "data"
    if data_src.exists():
        shutil.copytree(data_src, out_dir / "data")

    # README
    (out_dir / "README.md").write_text(
        _install_readme(list(mcp_servers))
    )


def _concat_skills(skills_root: Path) -> str:
    """Concatenate all skill bodies into a project-attachable instructions doc.

    Each skill becomes a section; references/ contents are inlined so the model
    has them in context without filesystem access.
    """
    parts: list[str] = []
    parts.append("# ncplot-agent — Project instructions\n")
    parts.append(
        "These are the skills the model should follow when working with NetCDF "
        "files in this project. They were generated from the canonical skills "
        "in the ncplot-agent repository. Refer to a skill by name when "
        "responding to a request that matches its `When to use` section.\n"
    )
    parts.append(
        "## Self-improvement loop (manual mode)\n"
        "Claude Desktop has no session-end hooks, so the skill-refiner runs "
        "manually. After a session with corrections or new patterns, ask: "
        "\"run the skill-refiner on this session\". The refiner writes draft "
        "patches to `.ncplot/refinements/` for review with `ncplot-refine`.\n"
    )

    for s in sorted(skills_root.iterdir()):
        if not s.is_dir():
            continue
        md = s / "SKILL.md"
        if not md.exists():
            continue
        text = md.read_text()
        m = FRONTMATTER_RE.match(text)
        if not m:
            continue
        body = m.group(2)
        parts.append(f"\n---\n\n# Skill: {s.name}\n\n")
        parts.append(body)

        # Inline references/
        refs_dir = s / "references"
        if refs_dir.exists():
            for ref in sorted(refs_dir.glob("*.md")):
                parts.append(f"\n### Reference: `references/{ref.name}`\n\n")
                parts.append(ref.read_text())

    return "".join(parts)


def _install_readme(mcps: list[str]) -> str:
    mcp_lines = "\n".join(f"  - `{m}`" for m in mcps) or "  (none)"
    return f"""# ncplot-agent — Claude Desktop integration

## What's in this directory

- `mcp_config_snippet.json` — merge into your Claude Desktop config
- `mcp-servers/` — Python source for the MCP servers
- `project_instructions.md` — attach to a Claude Project to get the skills
- `data/regions.json` — shared region definitions

## Install

1. **Pick an install path.** Copy this directory somewhere stable, e.g.
   `~/Library/Application Support/Claude/ncplot-agent/` (macOS).

2. **Edit `mcp_config_snippet.json`.** Replace every `INSTALL_PATH` with
   the absolute path you chose.

3. **Merge into Claude Desktop config:**
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%/Claude/claude_desktop_config.json`

   Merge the `mcpServers` keys; don't overwrite existing entries.

4. **Install MCP server dependencies:**
   ```
   pip install xarray netcdf4 cftime numpy matplotlib cartopy mcp
   ```

5. **Create a Project in Claude Desktop**, paste the contents of
   `project_instructions.md` into the project knowledge area.

6. Restart Claude Desktop. The MCP servers should appear as available tools.

## What works / doesn't here

| Feature                  | Supported                  |
|--------------------------|----------------------------|
| MCP servers              | yes (native)               |
| Skills                   | via project instructions   |
| Slash commands           | no (Desktop has none)      |
| Hooks (Stop, etc.)       | no                         |
| Auto-refinement          | no — invoke manually       |

MCP servers used:
{mcp_lines}
"""

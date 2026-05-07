"""Build the OpenAI Codex AGENTS.md bundle from src/.

Codex (and other AGENTS.md-aware agents) consumes a single AGENTS.md document
that describes the working environment, available tools, and procedures. This
builder concatenates skills into AGENTS.md and provides a setup script for the
MCP servers.

Status: stub. Generates a working AGENTS.md by concatenation; richer
integration (Codex tool definitions, sandbox config) is TODO.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path

OUT_NAME = "ncplot-agent-codex"

FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def build(src_root: Path, out_root: Path) -> None:
    out_dir = out_root / OUT_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Bundle MCP servers
    mcp_dst = out_dir / "mcp-servers"
    mcp_dst.mkdir()
    for m in sorted((src_root / "mcp").iterdir()):
        if not m.is_dir():
            continue
        shutil.copytree(m, mcp_dst / m.name)

    # Generate AGENTS.md
    agents_md = _generate_agents_md(src_root / "skills")
    (out_dir / "AGENTS.md").write_text(agents_md)

    # Setup script
    (out_dir / "setup.sh").write_text(
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "pip install xarray netcdf4 cftime numpy matplotlib cartopy mcp\n"
        "echo 'ncplot-agent dependencies installed.'\n"
    )
    (out_dir / "setup.sh").chmod(0o755)

    # Reference data
    if (src_root / "data").exists():
        shutil.copytree(src_root / "data", out_dir / "data")

    # README
    (out_dir / "README.md").write_text(_install_readme())


def _generate_agents_md(skills_root: Path) -> str:
    parts: list[str] = []
    parts.append(
        "# AGENTS.md — ncplot-agent\n\n"
        "This document gives the agent the procedural knowledge it needs to "
        "answer plotting requests against NetCDF files. It also describes the "
        "available MCP tools (netcdf-reader, plot-renderer) and the manual "
        "self-improvement loop.\n\n"
        "## Tools\n\n"
        "Two MCP servers are launched alongside this agent:\n\n"
        "- `netcdf-reader` — `inspect`, `read_slice`, `compute_stats`, `regrid_to_centers`\n"
        "- `plot-renderer` — `render_map`, `render_timeseries`, `render_profile`, "
        "`render_cross_section`, `render_hovmoller`\n\n"
        "## Procedures\n\n"
        "The skills below describe how to handle specific user request patterns. "
        "Match the user's request against each skill's *When to use* section "
        "and follow the matching procedure. Run `netcdf-inspect` first whenever "
        "a NetCDF file path appears for the first time in a session.\n"
    )

    for s in sorted(skills_root.iterdir()):
        if not s.is_dir():
            continue
        md = s / "SKILL.md"
        if not md.exists():
            continue
        m = FRONTMATTER_RE.match(md.read_text())
        if not m:
            continue
        parts.append(f"\n---\n\n## Skill: {s.name}\n\n")
        parts.append(m.group(2))

        refs_dir = s / "references"
        if refs_dir.exists():
            for ref in sorted(refs_dir.glob("*.md")):
                parts.append(f"\n### Reference: `references/{ref.name}`\n\n")
                parts.append(ref.read_text())

    parts.append(
        "\n---\n\n"
        "## Self-improvement loop\n\n"
        "After any session with corrections, surprises, or non-trivial problem "
        "solving, run the `skill-refiner` skill. It writes draft refinements "
        "to `.ncplot/refinements/` for review with `ncplot-refine`. Do not "
        "modify the canonical skill files in this AGENTS.md directly — the "
        "review/apply loop is what keeps the changes auditable.\n"
    )

    return "".join(parts)


def _install_readme() -> str:
    return """# ncplot-agent — Codex / AGENTS.md target

## Install

1. Copy `AGENTS.md` to your project root (or the directory where Codex starts).
2. Run `./setup.sh` to install MCP server dependencies.
3. Configure your Codex agent / OpenAI Agents SDK to launch the two MCP
   servers in `mcp-servers/`. (TODO: provide a ready-made agent config.)

## What's working

- AGENTS.md is generated from the canonical skills.
- MCP server source is bundled.

## What's not yet

- Auto-config for OpenAI Agents SDK / Codex CLI.
- Hook equivalent for auto-triggering the refiner.
"""

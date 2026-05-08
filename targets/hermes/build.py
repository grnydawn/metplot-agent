"""Build the Hermes Agent skill bundle from src/.

Hermes uses ~/.hermes/skills/<skill>/SKILL.md (agentskills.io standard), which
is the same format as the canonical sources. This builder is essentially a
copy + a Hermes-specific manifest fragment for the MCP servers.

Hermes has its own learning loop, so the skill-refiner here is wired to write
to .metplot/refinements/ rather than calling Hermes' skill_manage tool directly
— that way human review still happens.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

OUT_NAME = "metplot-hermes"


def build(src_root: Path, out_root: Path) -> None:
    out_dir = out_root / OUT_NAME
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Skills directory — direct copy
    skills_dst = out_dir / "skills"
    shutil.copytree(src_root / "skills", skills_dst)

    # MCP servers
    mcp_dst = out_dir / "mcp-servers"
    shutil.copytree(src_root / "mcp", mcp_dst)

    # Reference data
    if (src_root / "data").exists():
        shutil.copytree(src_root / "data", out_dir / "data")

    # Hermes MCP config — Hermes reads MCP servers from its config; emit a
    # snippet the user can merge.
    mcp_config = {
        "mcpServers": {
            "netcdf-reader": {
                "command": "python",
                "args": ["INSTALL_PATH/mcp-servers/netcdf-reader/server.py"],
            },
            "plot-renderer": {
                "command": "python",
                "args": ["INSTALL_PATH/mcp-servers/plot-renderer/server.py"],
            },
        }
    }
    (out_dir / "hermes_mcp_config.json").write_text(
        json.dumps(mcp_config, indent=2) + "\n"
    )

    (out_dir / "README.md").write_text(_install_readme())


def _install_readme() -> str:
    return """# metplot — Hermes Agent bundle

Hermes uses `~/.hermes/skills/` directly; the SKILL.md format is identical to
the canonical sources, so install is just a copy.

## Install

```
# 1. Copy skills into Hermes' skills directory
cp -r skills/* ~/.hermes/skills/

# 2. Pick a stable install path for the MCP servers, e.g.
INSTALL_PATH=~/.hermes/extras/metplot
mkdir -p $INSTALL_PATH
cp -r mcp-servers data $INSTALL_PATH/

# 3. Edit hermes_mcp_config.json: replace INSTALL_PATH placeholder.

# 4. Merge into your Hermes MCP config.

# 5. Install Python deps
pip install xarray netcdf4 cftime numpy matplotlib cartopy mcp
```

## Self-improvement loop

Hermes' built-in learning loop and our `skill-refiner` skill operate on
different layers:

- Hermes' loop creates *new* skills from session experience (general
  procedural memory).
- Our `skill-refiner` proposes *patches* to the existing canonical skills
  in this bundle, written as drafts to `.metplot/refinements/` for human
  review via `metplot-refine`.

Both can run side by side. Hermes' autonomous skills capture user-level
patterns; the canonical-skill refinements travel with the bundle and are
shareable.
"""

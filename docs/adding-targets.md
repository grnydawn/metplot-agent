# Adding a new target

A target is a build adapter that turns the canonical `src/` content into
a plugin format consumable by a specific agent host.

## Standard target template

After cycle 7, every target uses shared helpers from
`targets/_common/`. The skeleton:

```python
# targets/<host>/build.py
from __future__ import annotations

import json
import shutil
from pathlib import Path

from targets._common.manifest import (
    PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_DESCRIPTION,
    PLUGIN_HOMEPAGE, PLUGIN_LICENSE, PLUGIN_AUTHOR,
    common_metplot_block,
)
from targets._common.mcp_bundling import bundle_mcp_servers, MCP_SERVERS
from targets._common.skills import copy_skills
from targets._common.install_tooling import copy_install_tooling


def build(src_root: Path, out_root: Path) -> None:
    plugin_dir = out_root / PLUGIN_NAME
    if plugin_dir.exists():
        shutil.rmtree(plugin_dir)
    plugin_dir.mkdir(parents=True)

    # 1. Manifest (host-specific path + shape)
    # 2. copy_skills(src_root, plugin_dir / "skills")
    # 3. bundle_mcp_servers(src_root, plugin_dir / "mcp-servers")
    # After bundle_mcp_servers:
    copy_install_tooling(src_root.parent, plugin_dir)
    # 4. Host-specific MCP launch config (path + key name varies)
    # 5. Slash command (md / TOML / native)
    # 6. README
```

## Host-specific config files

| Host | MCP config path | MCP config key | Manifest path | Setup script | Setup command |
|------|-----------------|----------------|---------------|--------------|---------------|
| Claude Code | `.mcp.json` | `mcpServers` | `.claude-plugin/plugin.json` | `setup.sh` / `setup.ps1` | `/metplot:setup` |
| Codex | `config.toml` (TOML) | `[mcp_servers.X]` | `.codex-plugin/plugin.json` | `setup.sh` / `setup.ps1` | `/setup` |
| Gemini CLI | `settings.json` | `mcpServers` | `gemini-extension.json` (root) | `setup.sh` / `setup.ps1` | `/metplot:setup` |
| Cursor | `.cursor/mcp.json` | `mcpServers` | `.cursor-plugin/plugin.json` | `setup.sh` / `setup.ps1` | `/setup` |
| GitHub Copilot | `.vscode/mcp.json` | `servers` ⚠ | `plugin.json` (root) | `setup.sh` / `setup.ps1` | `/metplot:setup` |
| Antigravity | `mcp_config.json` (snippet) | `mcpServers` | n/a (no manifest) | `setup.sh` / `setup.ps1` | `/setup` workflow |
| Claude Desktop | `claude_desktop_config_snippet.json` | `mcpServers` | n/a (project doc) | `setup.sh` / `setup.ps1` | manual `./setup.sh` |

## Host-specific gotchas

- **Copilot uses `servers`, not `mcpServers`.** The only host with
  this naming. A regression test (`tests/targets/copilot/test_servers_key.py`)
  guards against accidental cross-target contamination.
- **Antigravity has no formal hook system.** Cycle-6 self-improvement
  degrades to a manual `/refine` workflow.
- **Claude Desktop has no skill loader.** Skills are concatenated into
  a project-instructions document. YAML frontmatter is stripped.
- **Codex slash-command authoring is undocumented.** We omit a
  `/refine` command on Codex pending a confirmed format.

## Test suite template

Each target gets `tests/targets/<host_underscore>/`:
- `conftest.py` — module-scoped `built_plugin` fixture
- `test_build_runs.py` — top-level structure
- `test_manifest.py` (or analog) — manifest shape
- `test_skills_copied.py` — allowlist + skill-refiner exclusion
- `test_mcp_servers_bundled.py` — re-rooted source + patched pyproject
- `test_<host>_mcp.py` — host-specific MCP config validation
- `test_commands.py` — slash command / workflow file
- `test_no_hooks.py` — cycle-6 deferral

## See also

- `docs/architecture.md` — overall L1/L2/L3 layering
- `docs/research/2026-05-08-multi-host-survey.md` — host plugin model
  research
- `targets/claude-code/build.py` — reference implementation
- `targets/_common/` — shared helpers

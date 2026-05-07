# Claude Code target

Build with:

```
python -m tools.build claude-code
```

Output lands in `build/claude-code/ncplot-agent/`. See the generated README
inside that directory for install instructions.

## What this builder produces

A complete Claude Code plugin:
- `.claude-plugin/plugin.json` manifest
- `skills/` — direct copies of the canonical SKILL.md packages
- `mcp-servers/` — bundled MCP server source + launch config
- `commands/refine.md` — `/refine` slash command
- `hooks/session_end_refiner.sh` — Stop hook for auto-refiner trigger
- `.mcp.json` — MCP server launch stanzas
- `data/` — shared reference data

See `build.py` for the assembly logic.

# metplot-agent

A multi-target AI agent plugin for natural-language plotting from NetCDF data files,
with a closed-loop skill-refinement layer that brings Hermes-style self-improvement
to agents that don't have it natively (Claude Code, Claude Desktop, Codex, Cursor).

> Status (as of cycle 6 Phase B): the five plotting skills, the two MCP
> servers, and six target builders (claude-code, cursor, copilot,
> gemini-cli, codex, antigravity, claude-desktop) are shipping. The
> closed-loop `skill-refiner` is shipping too, auto-fired by a `Stop`
> hook on Claude Code and manual-trigger via `/refine` on the other
> hosts (per-host hook coverage is a cycle 7+ candidate).

## What this is

A *plugin source* repository, not a plugin. The canonical content lives under `src/`
and is compiled into target-specific plugin packages by builders under `targets/`.

```
src/  ─────► tools/build.py ─────►  build/<target>/
                  │
                  ├── claude-code/   (plugin manifest + skills + MCP wiring)
                  ├── claude-desktop/ (MCP config + system prompt fragments)
                  ├── codex/          (AGENTS.md + scripts)
                  └── hermes/         (skills/ tree + MCP servers)
```

The "self-improvement" loop is implemented at the skill layer rather than the agent
layer — see `docs/self-improvement.md`. This makes it portable across agents.

## Layout

```
src/
├── skills/        SKILL.md packages (agentskills.io / Anthropic format)
│   ├── netcdf-inspect/        always run first on a new file
│   ├── netcdf-plot-router/    routes free-form plot requests to a sub-skill
│   ├── netcdf-plot-map/       2D lat/lon maps
│   ├── netcdf-plot-timeseries/ 1D time series
│   ├── netcdf-plot-profile/   vertical profiles & cross-sections
│   └── skill-refiner/         the closed-loop learning meta-skill
├── mcp/           MCP server implementations
│   ├── netcdf-reader/         inspect + slice NetCDF files
│   └── plot-renderer/         render matplotlib/cartopy figures
├── data/          shared reference data (regions, palettes, ...)

targets/
├── claude-code/   builds a Claude Code plugin (manifest + skills + hooks)
├── claude-desktop/ builds a Claude Desktop config snippet (MCP servers + project doc)
├── codex/         builds an OpenAI Codex AGENTS.md + tooling
└── hermes/        builds a Hermes skill bundle (~/.hermes/skills/...)

tools/
├── build.py       dispatcher: `python -m tools.build <target>`
└── lint_skills.py validates SKILL.md frontmatter and structure

docs/
├── architecture.md
├── self-improvement.md
└── adding-targets.md
```

## Quickstart

```bash
# install dev deps
pip install -e '.[dev]'

# lint all skills
python -m tools.lint_skills

# build for a specific target
python -m tools.build claude-code
python -m tools.build claude-desktop
python -m tools.build hermes

# build everything
make all
```

Build artifacts land in `build/<target>/` and are gitignored.

## Self-improvement loop

The `skill-refiner` skill is the closed-loop learning component. It runs after a
plotting task (manually invoked, or via a hook on supported targets) and proposes
patches to the canonical skills based on what was learned. Patches go to
`.metplot/refinements/` as draft markdown; a `tools/apply_refinements.py` review
step lets you accept/reject before they merge.

This is intentionally human-in-the-loop. For scientific work, an unattended
self-modifying skill set is a liability — silent failures in plotting code are
exactly what you don't want compounding without review. See
`docs/self-improvement.md` for the design rationale.

## Contributing & extending

- Add a new plot type → new skill under `src/skills/netcdf-plot-<name>/`,
  reference it from `netcdf-plot-router/SKILL.md`.
- Add a new agent target → new directory under `targets/<name>/` with a `build.py`
  exposing `build(src_root, out_root)`. Register it in `tools/build.py`.

## License

MIT — see `LICENSE`.

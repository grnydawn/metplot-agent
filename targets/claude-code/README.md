# Claude Code target

This target packages the canonical L1 source under `src/` (skills + MCP
servers + reference data) into an installable Claude Code plugin payload.

## Build

```
python -m tools.build claude-code
```

Output lands in `build/claude-code/ncplot-agent/`. See the README inside
that directory for end-user install instructions.

## Validate the build output

```
python -m tools.build claude-code --validate
```

Runs the cycle-4 test suite under `tests/targets/claude_code/` against
the freshly produced artifact. CI uses this; local development can skip
it.

## What this builder produces

A complete Claude Code plugin:

```
build/claude-code/ncplot-agent/
├── .claude-plugin/plugin.json   # manifest with cycle metadata
├── README.md                    # end-user install + setup instructions
├── skills/                      # 5 SKILL.md packages from cycle 3
├── mcp-servers/                 # netcdf_reader + plot_renderer (installable)
├── .mcp.json                    # MCP launch stanzas (entry-point scripts)
└── commands/refine.md           # /refine placeholder (full impl: cycle 6)
```

## Skill-refiner + Stop hook

Both are deferred to cycle 6. The cycle-4 build excludes
`src/skills/skill-refiner/` from the payload and produces no
`hooks/` directory. The `/refine` slash command stub is included so
the command name appears in autocomplete; its body explains that the
feature is on the way.

## MCP server packaging

The cycle-1/2 MCP servers ship as pip-installable Python distributions
under `mcp-servers/<name>/`. The build:

1. Re-roots the package source under `mcp-servers/<name>/src/mcp/<name>/`
   (preserving the `src.mcp.<name>` import path that server.py uses).
2. Patches the original `pyproject.toml` to add
   `[tool.setuptools.packages.find]` with `where = ["src"]` and
   `namespaces = true`.

The generated README instructs the end-user to `pip install` each
server, which puts the entry-point scripts (`ncplot-netcdf-reader`,
`ncplot-plot-renderer`) on PATH. The `.mcp.json` launch commands
reference these.

For developers who don't want a system-wide pip install, they can
substitute a `python -m src.mcp.<name>.server` invocation in
`.mcp.json`, with `${CLAUDE_PLUGIN_ROOT}/mcp-servers/<name>/src/` on
`PYTHONPATH`. The default config uses entry-points; the alternative
is documented in the plugin README.

## Cycle 5: dependency installer

Cartopy and scipy are scientific Python deps with C-level requirements
(PROJ, GEOS, BLAS). Installing them robustly across platforms is
non-trivial; cycle 5 ships a setup helper. Until then, the plugin
README points users to conda-forge and pip with documented fallbacks.

## See also

- `docs/architecture.md` — overall L1/L2/L3 layering
- `docs/adding-targets.md` — adding more targets (claude-desktop, codex, hermes, cursor)
- `docs/specs/2026-05-08-cycle-4-claude-code.md` — cycle-4 design

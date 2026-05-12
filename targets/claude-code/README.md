# Claude Code target

This target packages the canonical L1 source under `src/` (skills + MCP
servers + reference data) into an installable Claude Code plugin payload.

## Build

```
python -m tools.build claude-code
```

Output lands in `build/claude-code/metplot/`. See the README inside
that directory for end-user install instructions.

## Validate the build output

```
python -m tools.build claude-code --validate
```

Runs the cycle-4 test suite under `tests/targets/claude_code/` against
the freshly produced artifact. CI uses this; local development can skip
it.

## What this builder produces

A complete Claude Code plugin alongside a sibling marketplace
manifest, so `build/claude-code/` is itself an installable Claude
Code plugin marketplace:

```
build/claude-code/
├── .claude-plugin/marketplace.json  # marketplace listing metplot
└── metplot/
    ├── .claude-plugin/plugin.json   # manifest with cycle metadata
    ├── README.md                    # end-user install + setup instructions
    ├── skills/                      # 6 SKILL.md packages (5 plotting + skill-refiner)
    ├── mcp-servers/                 # netcdf_reader + plot_renderer (installable)
    ├── .mcp.json                    # MCP launch stanzas (entry-point scripts)
    ├── commands/                    # /metplot:setup, /metplot:refine
    └── hooks/                       # SessionStart (setup) + Stop (refine) hooks
```

End users register the build dir as a marketplace and install via
`/plugin`:

```text
/plugin marketplace add /absolute/path/to/metplot-agent/build/claude-code
/plugin install metplot@metplot-local
```

The marketplace name (`metplot-local`) is exported as
`MARKETPLACE_NAME` in `build.py`.

## Skill-refiner + Stop hook (shipped cycle 6 Phase B)

The build ships `src/skills/skill-refiner/` in the plugin payload
and emits `hooks/refine.json` registering a `Stop` matcher that
spawns a fresh subagent running `/metplot:refine` at session end.
The subagent invocation is backgrounded (`nohup … &`) so it never
blocks the parent session, guards against missing `claude` on PATH,
and always `exit 0`s so a refiner hiccup can't break the host's
session-end flow. The `/refine` slash command body procedurally
routes the agent at the skill, reads `.metplot/task-log.jsonl`, and
writes drafts to `.metplot/refinements/` for human review via
`metplot-refine`.

Other hosts ship `skill-refiner` too (the allowlist is shared) but
their `/refine` bodies note the manual-trigger nature — only Claude
Code wires the native `Stop` hook in cycle 6.

## MCP server packaging

The cycle-1/2 MCP servers ship as pip-installable Python distributions
under `mcp-servers/<name>/`. The build:

1. Re-roots the package source under `mcp-servers/<name>/src/mcp/<name>/`
   (preserving the `src.mcp.<name>` import path that server.py uses).
2. Patches the original `pyproject.toml` to add
   `[tool.setuptools.packages.find]` with `include = ["src", "src.*"]`
   and `namespaces = true` (cycle-6 task 2 fixed the earlier
   `where = ["src"]` form, which stripped the `src.` prefix and broke
   `import src.mcp.<name>...`).

The generated README instructs the end-user to `pip install` each
server, which puts the entry-point scripts (`metplot-netcdf-reader`,
`metplot-plot-renderer`) on PATH. The `.mcp.json` launch commands
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

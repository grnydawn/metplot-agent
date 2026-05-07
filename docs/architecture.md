# Architecture

## Goal

Make natural-language NetCDF plotting *easy and reliable* across multiple AI agent
hosts (Claude Code, Claude Desktop, Codex, Cursor, Hermes, ...) without rewriting
the plotting logic for each one.

## Design

### Three layers

```
┌─────────────────────────────────────────────────────────────┐
│  L3: Agent host          (Claude Code / Desktop / Codex...)  │
│      provides: model, tool runtime, skill loader             │
├─────────────────────────────────────────────────────────────┤
│  L2: Plugin payload      (per-target build artifact)         │
│      contains: skills, MCP wiring, hooks, manifest           │
├─────────────────────────────────────────────────────────────┤
│  L1: Canonical source    (this repo, src/)                   │
│      contains: SKILL.md, MCP servers, references, scripts    │
└─────────────────────────────────────────────────────────────┘
```

The plugin payload (L2) is what each target builder produces. The same L1 source
flows into every target. Skill bodies are largely identical across targets — only
manifest format, install path, and hook invocation differ.

### Why this works

- Anthropic's SKILL.md format and Hermes' agentskills.io format are nearly identical:
  YAML frontmatter (name, description) + markdown body, with a directory of
  optional `references/`, `scripts/`, `assets/`. The same SKILL.md file is valid
  for both with no transformation.
- MCP is the standard tool-server protocol across Claude Code, Claude Desktop,
  Codex (via OpenAI Agents SDK), Cursor, and Hermes. One MCP implementation, many
  consumers.
- Where targets diverge (slash command syntax, hook event names, manifest schema),
  the divergence lives in `targets/<name>/build.py`.

### Skill graph

```
                  user request
                        │
                        ▼
              netcdf-plot-router  ◄── triages free-form requests
                        │
        ┌───────────────┼───────────────┐
        ▼               ▼               ▼
  netcdf-plot-map  ...-timeseries  ...-profile
        │               │               │
        └───────┬───────┴───────┬───────┘
                ▼               ▼
       netcdf-inspect      MCP: plot-renderer
       (always run on              │
        new file paths)            ▼
                ▼              figure file
       MCP: netcdf-reader
                │
                ▼
        file metadata + slices
```

### MCP server boundaries

- `netcdf-reader` — pure data: list variables, dump metadata, read slices,
  compute simple stats. No plotting.
- `plot-renderer` — pure rendering: takes a structured spec (variable values,
  coords, projection, colormap) and returns a figure file. Doesn't know about
  NetCDF.

This separation means either MCP can be swapped (e.g., a Zarr reader instead of
NetCDF, or a plotly renderer instead of matplotlib) without touching the other.

## Self-improvement layer

See `self-improvement.md` for the full design. The short version:

- The `skill-refiner` skill examines a completed plotting task and proposes
  patches to the relevant SKILL.md files (new aliases discovered, pitfalls hit,
  preferences expressed).
- Patches are written as drafts to `.ncplot/refinements/` (gitignored, local).
- A review CLI (`ncplot-refine`) shows diffs and applies accepted patches to
  the canonical `src/skills/`.
- The next build picks them up.

This is intentionally human-reviewed. Hermes' fully-autonomous skill writes are
a feature for general productivity work; for scientific plotting they're a
liability because subtly wrong refinements compound silently.

## Target-specific notes

| Target          | Skills        | MCP    | Hooks    | Refiner trigger     |
|-----------------|---------------|--------|----------|---------------------|
| Claude Code     | native        | native | native   | Stop hook (auto)    |
| Claude Desktop  | via project doc | native | none   | manual `/refine`    |
| Codex           | AGENTS.md     | via SDK| via SDK  | manual              |
| Cursor          | rules dir     | native | limited  | manual              |
| Hermes          | native        | native | native   | built-in loop       |

For agents without native skill loaders, we concatenate skill content into a
project-level instruction document (Claude Desktop) or AGENTS.md (Codex) at
build time.

## Non-goals

- Not a general scientific computing agent. Focus is plotting from NetCDF files.
  Other formats (Zarr, GRIB, HDF5) are reachable by writing additional MCP
  readers but are not in scope here.
- Not a replacement for domain-specific simulation agents (JutulGPT, MooseAgent,
  etc.). This is a thin user-facing layer; deep solver-aware verification is a
  separate problem.
- Not aiming for full autonomy in the refinement loop. Human review is part of
  the design, not a workaround.

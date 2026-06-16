# metplot-agent

## What this project is

`metplot-agent` is a multi-agent AI plugin for NetCDF file inspection and visualization. It enables natural language plotting across seven AI coding agents (Claude Code, Cursor, GitHub Copilot, Gemini CLI, Codex, Antigravity, Claude Desktop) through a unified Model Context Protocol (MCP) backend, with built-in support for structured mesh formats (MPAS, WRF, ROMS) and self-improving skill refinement via task logging.

## Stack & key dependencies

**Core:**
- Python 3.10+
- PyYAML 6.0+ (configuration)
- Click 8.1+ (CLI tools)

**MCP servers (optional, required for plotting):**
- mcp 1.0+
- xarray 2024.1+ (NetCDF data model)
- netcdf4 1.6+ (HDF5/NetCDF I/O)
- numpy 1.24+ (numerical arrays)
- matplotlib 3.8+ (raster rendering)
- cartopy 0.22+ (map projections)

**Development:**
- pytest 7.4+ (testing)
- ruff 0.4+ (linting)
- mypy 1.8+ (type checking)

## Repository layout

- **`src/`** — canonical source tree
  - `skills/` — skill definitions (netcdf-inspect, netcdf-plot-map, netcdf-plot-profile, netcdf-plot-timeseries, netcdf-plot-router, skill-refiner); each skill has `SKILL.md` spec, `references/` data, and `scripts/` implementation
  - `mcp/` — MCP server packages (netcdf_reader, plot_renderer)
  - `ssh_broker/` — SSH broker for secure remote file access (paramiko-based, drops credentials post-auth)
  - `data/` — reference data (regions, colormaps, aliases)
- **`targets/`** — build adapters (one per agent host); convert `src/` artifacts to target-specific config formats
- **`tools/`** — build and deployment scripts (`build.py`, `install_deps.py`, `apply_refinements.py`, `lint_skills.py`)
- **`tests/`** — pytest suite, including `golden/` reference PNGs for image-diff regression tests
- **`.claude/`** — Claude Code harness config and autonomous build-pipeline skills (super-board, super-build, super-qa, super-review)
- **`docs/`** — user and contributor documentation

## Conventions

**Testing framework:** pytest (7.4+) with custom markers
- `@pytest.mark.image_diff` for visual regression tests (opt-in via `--image-diff` CLI flag)
- Optional `--regenerate-golden` to update reference PNGs
- `testpaths = ["tests"]`

**Code organization:**
- Skill specs live in `src/skills/*/SKILL.md`; reference data in `src/skills/*/references/`; implementation in `src/skills/*/scripts/`
- MCP servers are standalone Python packages in `src/mcp/*/`
- Type checking via mypy, linting via ruff (100-char line length)

**Branching & commit style:**
- Main branch: `master`
- Feature branches follow cycle pattern: `cycle-N-feature-name` (e.g. `cycle-14-impl`, `cycle-8-phase-b`)
- Conventional commit prefixes: `feat()`, `fix()`, `test()`, `docs()`, `refactor()`
- PRs require passing lint + test before merge

## Success criteria for a change

A change is "done" when:

1. **Tests pass:** `pytest -q` (or `make test`)
2. **Linting passes:** ruff/mypy checks and `make lint` (SKILL.md format validation)
3. **If touching skills:** `metplot-lint` validates SKILL.md manifest structure
4. **If adding/modifying MCP logic:** unit tests in `tests/mcp/` pass
5. **If visual rendering changed:** image-diff tests pass (`pytest --image-diff`)
6. **If touching targets:** `python -m tools.build <target>` produces a valid bundle
7. **Pre-commit:** both `make lint` and `make test` pass before opening a PR

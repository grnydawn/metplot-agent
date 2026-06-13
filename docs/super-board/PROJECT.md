# PROJECT.md — metplot-agent

## What it is

`metplot-agent` is a multi-target AI-agent plugin that adds NetCDF plotting via natural language to AI coding agents (Claude Code, Cursor, GitHub Copilot, Gemini CLI, Codex, Antigravity, Claude Desktop). A user says things like "Inspect this file" or "Plot sea surface temperature over the North Atlantic," and the agent walks the file, slices the data, and renders a PNG. It is MPAS/unstructured-mesh aware and ships skills plus two MCP servers (a NetCDF reader and a plot renderer). A single canonical source repo (`src/`) is compiled into seven host-specific build targets, and skills are self-improving through a refiner loop.

## Stack

- **Language:** Python, `requires-python >= 3.10` (ruff/mypy target `py310`).
- **Build/packaging:** setuptools (`setuptools.build_meta`), PEP 621 `pyproject.toml`; `uv.lock` present. A `Makefile` wraps common tasks.
- **Core deps:** `pyyaml`, `click`.
- **Optional `mcp` extra (MCP-server runtime):** `mcp`, `xarray`, `netcdf4`, `numpy`, `matplotlib`, `cartopy`. Remote-file access uses `paramiko` via the `metplot-ssh-broker`.
- **Optional `cycle8-poc` extra:** `uxarray`, `datashader` (unstructured-mesh PoC; transitional).
- **Architecture:** L1/L2/L3 layering (see `docs/architecture.md`); `src/` is canonical, `targets/` are build adapters, `build/` is generated (gitignored).

## Conventions

- **Testing:** `pytest` (`make test`, or `pytest -q`). Tests live in `tests/`; `pythonpath = ["."]`, `addopts = "-ra"`. A custom `image_diff` marker gates image-diff tests (run with `--image-diff`). Golden fixtures under `tests/golden/`.
- **Lint/format:** `ruff` (line length 100). **Type-check:** `mypy` (namespace packages; several third-party modules lack stubs and are ignored). Skill-manifest validation: `python -m tools.lint_skills` / `make lint`.
- **Entry points (CLI scripts):** `metplot-build` (`tools.build:cli`), `metplot-lint` (`tools.lint_skills:cli`), `metplot-refine` (`tools.apply_refinements:cli`). Build a target with `python -m tools.build <target>`.
- **Source layout:** Edit skills/MCPs/reference data in `src/`; edit `targets/` only when adding a host or fixing a target-specific quirk. Never commit `build/` or `.metplot/` (runtime state).
- **Refinement workflow:** real plotting work logs corrections to `.metplot/task-log.jsonl`; the `skill-refiner` skill produces drafts under `.metplot/refinements/`; review/apply with `metplot-refine`, then commit accepted changes to `src/skills/`.
- **Commit/PR:** Pre-commit checks are `make lint` and `make test`. PRs touching `src/skills/` should note whether the change came from a refinement (link the draft) or was hand-written.

## Success criteria

A typical ticket is "done" when:
- `make test` (pytest) passes, including any relevant golden/image-diff tests.
- `make lint` (skill-manifest validation) is clean, and `ruff` + `mypy` pass.
- The change is made in the canonical `src/` tree (not in generated `build/` or in `targets/` unless host-specific), and affected build targets still build via `python -m tools.build <target>`.
- The feature behaves as described end-to-end (e.g., inspect → slice → render produces the expected plot), and skill changes are documented per the refinement note.

## Board conventions (super-board)

The GitHub Project board uses one column beyond the standard super-board set:

- **Backlog** — a *staging* column. `super-board run` never dispatches Backlog
  cards: the wave planner (`super-board-wave-plan.sh`) only pulls from
  `Ready`/`QA`/`Review`, so anything in Backlog sits untouched by workers.
  `super-board lint` **does** scan Backlog, so you can park rough or future
  tickets there and sharpen their acceptance criteria before promoting them.
  Workflow: draft in **Backlog** → `super-board lint` → move to **Ready** when
  it's ready for the autonomous loop.

  Note: the lint-side scan of Backlog is configured in the installed super-board
  skill (`references/lint.md`), which lives under the gitignored `.claude/` tree;
  re-apply it after a skill upgrade if lint stops scanning Backlog.

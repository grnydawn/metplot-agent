# metplot-agent — Tester's Guide

A feature-coverage QA reference for `metplot-agent`. Each section
lists prompts the agent should accept, plus the **expected
behavior** — what the agent should do, what MCP tools it should
call, and what the response envelope or PNG output should look
like.

> **Scope distinction**: this is the *feature-coverage* tester's
> guide. The dogfood-tester's guide (`docs/dogfood-tester-guide.md`)
> is the cycle-scoped guide for skill-refiner self-improvement
> loop dogfooding. Both are useful; use whichever fits your task.

## How to use this guide

Each entry is shaped as:

> **Test N.M** — short title
>
> **Setup** (if applicable): file paths, install state, etc.
>
> **You**: the prompt to type into the agent
>
> **Expected**: bullet list of what should happen, including the
> MCP tools called, the response envelope shape, and any
> user-visible output.

Tests are organized by capability area. Start with §1
(installation) on a fresh host, then walk down the areas
relevant to your QA scope. Real example NetCDF files are
referenced where possible; for synthetic-only tests we point at
fixtures in `tests/mcp/netcdf_reader/conftest.py`.

## Conventions in this guide

- `<…>` are placeholders the tester fills in for their machine.
- "**Expected**: it calls X, then Y" means a tool-call trace
  where the agent invokes MCP tool X followed by Y.
- "✓" lines are pass criteria.
- Failed expectations should produce a finding under the
  category `failure_mode` in
  `docs/research/<DATE>-<short>.md` (see `docs/dogfood-tester-guide.md`
  for the format).

---

## Table of contents

1. [Installation per host (7 hosts × fresh + reinstall)](#1-installation-per-host)
2. [Setup helper (`/metplot:setup`)](#2-setup-helper)
3. [Inspect — by file convention](#3-inspect--by-file-convention)
4. [Read slice](#4-read-slice)
5. [Variable & time resolution](#5-variable--time-resolution)
6. [Plot maps — rectilinear](#6-plot-maps--rectilinear)
7. [Plot maps — curvilinear (WRF, ROMS)](#7-plot-maps--curvilinear-wrf-roms)
8. [Plot maps — unstructured (MPAS family)](#8-plot-maps--unstructured-mpas-family)
9. [Mesh-pairing flow](#9-mesh-pairing-flow)
10. [Time-series plots](#10-time-series-plots)
11. [Vertical profile plots](#11-vertical-profile-plots)
12. [Regions & longitude convention](#12-regions--longitude-convention)
13. [Vertical level selection](#13-vertical-level-selection)
14. [Multi-file glob (time-concat)](#14-multi-file-glob-time-concat)
15. [Style by reference](#15-style-by-reference)
16. [Remote files (HTTPS, SSH)](#16-remote-files-https-ssh)
17. [Skill-refiner loop](#17-skill-refiner-loop)
18. [Refinement applier (`metplot-refine`)](#18-refinement-applier)
19. [Uninstall + clean reinstall](#19-uninstall--clean-reinstall)
20. [Failure modes & error envelopes](#20-failure-modes--error-envelopes)
21. [Real-data scenarios (`data/omega/`, `data/e3sm/`)](#21-real-data-scenarios-dataomega-datae3sm)

---

## 1. Installation per host

### 1.1 Claude Code fresh install

**Setup**: no prior metplot install. Repo cloned at
`~/repos/metplot-agent`.

**You**: (from shell) `python -m tools.build claude-code`

**Expected**:
- ✓ Stdout shows `building claude-code → build/claude-code`, then `done.`
- ✓ Directory `build/claude-code/metplot/` exists.
- ✓ `build/claude-code/.claude-plugin/marketplace.json` exists.
- ✓ `build/claude-code/metplot/skills/` contains 6 dirs:
  `netcdf-inspect`, `netcdf-plot-router`, `netcdf-plot-map`,
  `netcdf-plot-timeseries`, `netcdf-plot-profile`, `skill-refiner`.
- ✓ `build/claude-code/metplot/hooks/refine.json` and
  `hooks/setup.json` exist.
- ✓ `build/claude-code/metplot/commands/refine.md` and
  `commands/setup.md` exist.

In Claude Code:

**You**: `/plugin marketplace add /home/me/repos/metplot-agent/build/claude-code`

**Expected**:
- ✓ Claude Code reports "metplot-local marketplace added".

**You**: `/plugin install metplot@metplot-local`

**Expected**:
- ✓ Plugin installs.
- ✓ After restart, `claude mcp list` reports `metplot-netcdf-reader`
  and `metplot-plot-renderer` both ✓ Connected.
- ✓ Typing `/` in the prompt shows `/metplot:setup` and
  `/metplot:refine` in autocomplete.

### 1.2 Cursor fresh install

**You**: (from shell) `python -m tools.build cursor`

**Expected**:
- ✓ `build/cursor/metplot/.cursor-plugin/plugin.json` exists.
- ✓ `build/cursor/metplot/.cursor/mcp.json` exists.
- ✓ `build/cursor/metplot/skills/skill-refiner/` exists.
- ✓ `build/cursor/metplot/commands/refine.md` and
  `commands/setup.md` exist; bodies contain no `placeholder` /
  `cycle 6` tokens.

### 1.3 GitHub Copilot (VS Code) fresh install

**You**: `python -m tools.build copilot`

**Expected**:
- ✓ `build/copilot/metplot/plugin.json` exists at the plugin
  root (NOT `.copilot-plugin/`).
- ✓ `build/copilot/metplot/.vscode/mcp.json` exists and uses
  the `servers` key, NOT `mcpServers` (Copilot-specific naming
  per cycle 7).

### 1.4 Gemini CLI fresh install

**You**: `python -m tools.build gemini-cli`

**Expected**:
- ✓ `build/gemini-cli/metplot/gemini-extension.json` exists.
- ✓ `build/gemini-cli/metplot/commands/metplot/setup.toml` and
  `commands/metplot/refine.toml` exist (not at top-level
  `commands/`, but under the `metplot/` subdir — cycle 5
  rename).
- ✓ `build/gemini-cli/metplot/settings.json` exists with an
  `mcpServers` block.

### 1.5 Codex fresh install

**You**: `python -m tools.build codex`

**Expected**:
- ✓ `build/codex/metplot/.codex-plugin/plugin.json` exists.
- ✓ `build/codex/metplot/config.toml` exists with
  `[mcp_servers.metplot-netcdf-reader]` and
  `[mcp_servers.metplot-plot-renderer]` blocks.
- ✓ No `/refine` slash command file (Codex's slash-command
  authoring format is undocumented; cycle 7 §8.2).
- ✓ README has a "Known limitations" section noting Codex's
  slash-command gap.

### 1.6 Antigravity fresh install

**You**: `python -m tools.build antigravity`

**Expected**:
- ✓ `build/antigravity/metplot/.agent/skills/` contains all
  6 skill dirs.
- ✓ `build/antigravity/metplot/.agent/workflows/refine.md` and
  `workflows/setup.md` exist.
- ✓ `build/antigravity/metplot/mcp_config.json` snippet exists.
- ✓ No `plugin.json` manifest (Antigravity has no formal manifest
  format per cycle 7).

### 1.7 Claude Desktop fresh install

**You**: `python -m tools.build claude-desktop`

**Expected**:
- ✓ `build/claude-desktop/metplot/project_instructions.md`
  exists, containing all 6 skills concatenated with their YAML
  frontmatter stripped.
- ✓ `build/claude-desktop/metplot/claude_desktop_config_snippet.json`
  has an `mcpServers` block.

### 1.8 Build all at once

**You**: `python -m tools.build --all` (or `make all`)

**Expected**:
- ✓ Builds every target sequentially, no failures.
- ✓ `build/<target>/` exists for each of the 7 hosts.

---

## 2. Setup helper

### 2.1 Setup on a clean machine

**Setup**: machine without cartopy, scipy, or the metplot MCP servers
installed.

**You** (in agent): `/metplot:setup`

**Expected**:
- ✓ Agent runs the bundled `setup.sh`.
- ✓ Installs `cartopy`, `scipy`, and entry-point-bearing pip
  packages `metplot-netcdf-reader`, `metplot-plot-renderer` (and
  pulls in numpy, xarray, netcdf4, matplotlib as transitive deps).
- ✓ Exit status 0 on success.
- ✓ After completion, `which metplot-netcdf-reader` returns a
  path inside the active venv (or system Python's bin dir).

### 2.2 Setup idempotency

**You**: `/metplot:setup` (twice in a row)

**Expected**:
- ✓ Second invocation completes much faster.
- ✓ No re-install of already-satisfied packages.

### 2.3 Setup with optional opt-out

**You** (shell): `./setup.sh --no-cartopy --no-scipy`

**Expected**:
- ✓ Skips the heavy optional packages.
- ✓ Still installs the MCP servers.
- ✓ Subsequent map-plot attempts produce an `ambiguous`
  envelope with `subcode: cartopy_missing` and an install-command
  candidate.

---

## 3. Inspect — by file convention

### 3.1 Rectilinear CF (synthetic)

**Setup**: a synthetic 3-D CF file at `/tmp/era5.nc` with dims
`(time=365, lat=181, lon=360)`, variable `t2m`.

**You**: Inspect `/tmp/era5.nc`.

**Expected**:
- ✓ Tool call `netcdf-reader.inspect(path=…)`.
- ✓ Envelope: `ok=true`.
- ✓ `result.convention.primary = "CF"` with high confidence.
- ✓ `result.spatial.coord_kind = "rectilinear"`,
  `lat_name = "lat"`, `lon_name = "lon"`.
- ✓ Agent surfaces: variable count, time range, lon convention,
  any warnings.

### 3.2 CMIP6

**Setup**: a CMIP6 historical file (e.g. `tas_Amon_*.nc`).

**You**: What's in `<cmip6_file>`?

**Expected**:
- ✓ `convention.primary = "CMIP"`, evidence cites `mip_era` and
  `cmor_version` attrs.

### 3.3 WRF output

**Setup**: a WRF history file with `TITLE = "OUTPUT FROM WRF…"`,
2-D `XLAT`/`XLONG`, U on `west_east_stag`.

**You**: Inspect this WRF file: `<path>`.

**Expected**:
- ✓ `convention.primary = "WRF"`.
- ✓ `spatial.coord_kind = "curvilinear"`,
  `lat_name = "XLAT"`, `lon_name = "XLONG"`.
- ✓ Variable `U` has `grid_kind = "U"` and `is_staggered = true`.
- ✓ Variable `T2` has `grid_kind = "scalar"`,
  `is_staggered = false`.

### 3.4 ROMS output

**Setup**: ROMS history file with `s_rho`/`Cs_r` and 2-D `lat_rho`.

**You**: Inspect `<roms_file>`.

**Expected**:
- ✓ `convention.primary = "ROMS"`.
- ✓ `vertical.kind = "sigma"`, `vertical.name = "s_rho"`.
- ✓ `spatial.coord_kind = "curvilinear"`,
  `lat_name = "lat_rho"`.

### 3.5 MPAS-Ocean mesh file

**Setup**: `ocean_mesh.nc` — has `Conventions: MPAS`, lowercase
`nCells`, `latCell`/`lonCell`/`verticesOnCell`.

**You**: Inspect `/data/ocean_mesh.nc`.

**Expected**:
- ✓ `convention.primary = "MPAS"`, high confidence.
- ✓ `spatial.coord_kind = "unstructured"`.
- ✓ `spatial.cell_dim = "nCells"`, `n_cells = 7153`.
- ✓ `spatial.lat_var = "latCell"`, `lon_var = "lonCell"`.
- ✓ `spatial.vertex_lat_var = "latVertex"`,
  `vertex_lon_var = "lonVertex"`,
  `vertices_on_cell_var = "verticesOnCell"`.
- ✓ `spatial.lat_range` in degrees (converted from radians).
- ✓ `spatial.lon_range` in degrees, `lon_convention = "0..360"`.

### 3.6 MPAS-Ocean history (no mesh) — ambiguous envelope

**Setup**: `ocn.hist.0001-02-01_00.00.00.nc` alone, NO matching
mesh in the same dir.

**You**: Inspect `/data/ocn.hist.0001-02-01_00.00.00.nc`.

**Expected**:
- ✓ Envelope: `ok=false`.
- ✓ `error.code = "ambiguous"`.
- ✓ `error.subcode = "mesh_pairing_required"`.
- ✓ `error.candidates` is `[]` (no sibling mesh).
- ✓ `error.retry_with_param = "mesh_path"`.
- ✓ Agent surfaces: needs a mesh_path; lists `variables_in_history`
  from context.

### 3.7 MPAS-Ocean history (mesh sibling present)

**Setup**: `ocn.hist.0001-02-01_00.00.00.nc` AND `ocean_mesh.nc`
in the same directory.

**You**: Inspect `/data/ocn.hist.0001-02-01_00.00.00.nc`.

**Expected**:
- ✓ Envelope: `ok=false`, `subcode = "mesh_pairing_required"`.
- ✓ `error.candidates` contains `{value: ".../ocean_mesh.nc",
  param: "mesh_path", confidence: 0.7}`.
- ✓ Agent prompts the user to confirm or supply a different
  mesh_path.

### 3.8 MPAS history + mesh paired call

**Setup**: same files as 3.7.

**You**: Inspect `/data/ocn.hist.0001-02-01_00.00.00.nc` using
`/data/ocean_mesh.nc` as the mesh.

**Expected**:
- ✓ Tool call `inspect(path=…, mesh_path=…)`.
- ✓ Envelope: `ok=true`.
- ✓ `result.files = [history, mesh]`.
- ✓ `result.convention.primary = "MPAS"`.
- ✓ `result.spatial.coord_kind = "unstructured"`,
  `n_cells = 7153`.
- ✓ `Temperature`, `Salinity`, `SshCell` in `result.variables`
  tagged `grid_kind: "cell_centered"`.
- ✓ `NormalVelocity` (on `NEdges`) NOT tagged cell_centered.

### 3.9 Missing file

**You**: Inspect `/nonexistent/path.nc`.

**Expected**:
- ✓ Envelope: `ok=false`.
- ✓ `error.code = "file_not_found"`.

### 3.10 Unknown convention (CICE-style)

**Setup**: `cice.nc` with `ni=235160, nj=1`, no `Conventions`
attr, no `standard_name` on variables.

**You**: Inspect `cice.nc`.

**Expected**:
- ✓ `ok=true` (degraded, not a hard fail).
- ✓ `convention.primary = "unknown"`, confidence 1.0.
- ✓ `spatial = null` (no lat/lon detected).
- ✓ All variables' `long_name` and `standard_name` are `null`
  (placeholder-string normalization per cycle-6 task 3 step 2).

### 3.11 EAMxx (dual-grid)

**Setup**: `eamxx.nc` with `Conventions: CF-1.8`, `ncol` dim,
`elem × gp × gp` dycore dims.

**You**: Inspect `eamxx.nc`.

**Expected**:
- ✓ `ok=true`.
- ✓ `convention.primary = "CF"` (cycle 8 doesn't yet detect
  EAMxx as a separate convention).
- ✓ Most variables' `long_name`/`standard_name` are `null`
  (EAMxx ships them as the literal string "MISSING"; cycle-6
  normalization handles).
- ✓ Agent surfaces: dual-grid layout suspected (mentions `ncol`
  + spectral element); refers user to cycle-9 scope.

### 3.12 Inspection cache

**Setup**: a synthetic CF file at `/tmp/cf.nc`.

**You**: Inspect `/tmp/cf.nc` (twice).

**Expected**:
- ✓ First call: full open + parse.
- ✓ Second call: served from `.metplot/inspections/<hash>.json`.
  No xarray.open_dataset call.
- ✓ File-mtime change triggers re-inspect (cache invalidation).

---

## 4. Read slice

### 4.1 Inline form (small slice)

**You**: Read t2m at `time="first"`, `level=0`, region "global"
from `/tmp/cf.nc`.

**Expected**:
- ✓ `read_slice` returns `result.form = "inline"`.
- ✓ `result.values` is a JSON list/array.
- ✓ `result.stats` has min/max/mean/fraction_nan.
- ✓ `result.units` matches the file's attr.

### 4.2 File form (large slice)

**You**: Read t2m for the whole year (no time index, no region).

**Expected**:
- ✓ `result.form = "file"`.
- ✓ `result.path` is under `.metplot/slices/`.
- ✓ `result.size_bytes` reasonable for the shape.

### 4.3 MPAS paired slice

**Setup**: hist + mesh.

**You**: Read Temperature at the first time, surface layer, with
mesh `/data/ocean_mesh.nc`.

**Expected**:
- ✓ `read_slice(..., mesh_path=mesh)` succeeds.
- ✓ `result.dims = ["NCells"]`, `shape = [7153]`.
- ✓ `result.mesh_path` echoed in the result (so the renderer
  can pick it up).

### 4.4 Region subset

**You**: Read t2m for the North Atlantic, time=first.

**Expected**:
- ✓ Slice limited to the North-Atlantic bbox.
- ✓ `lat_indices` and `lon_indices` reflected in the resolved
  spec.
- ✓ Smaller output shape than the global slice.

### 4.5 Empty slice

**You**: Read t2m for a region entirely outside the file's
coverage.

**Expected**:
- ✓ Either `read_slice` returns success with `shape:[0,0]` and
  `stats: all None`, OR `render_map` returns `ambiguous`
  `empty_slice` if the user goes on to plot.

---

## 5. Variable & time resolution

### 5.1 Alias lookup — SST in CMIP

**Setup**: a CMIP file with variable `tos`.

**You**: Plot SST for September 2024.

**Expected**:
- ✓ Agent consults
  `src/skills/netcdf-inspect/references/aliases.md`.
- ✓ Picks `tos` automatically (informal → canonical alias).
- ✓ Says so explicitly: "SST resolved to `tos` via the CMIP6 alias".

### 5.2 Alias lookup — SST in OISST

**Setup**: a NOAA OISST file with variable `sst`.

**You**: Plot SST for last month.

**Expected**:
- ✓ Picks `sst` (the file uses the OISST convention).

### 5.3 Ambiguous variable

**Setup**: a file with both `tos` and `analysed_sst`.

**You**: Plot SST.

**Expected**:
- ✓ Returns `ambiguous` envelope, subcode `variable`.
- ✓ `candidates` lists `tos` and `analysed_sst` with `long_name`
  and `units` so the user can pick.
- ✓ Agent surfaces the choice.

### 5.4 Time as ISO

**You**: Plot t2m for 2024-09-15T12:00:00Z.

**Expected**:
- ✓ `find_time` resolves to exact match if the file has hourly
  data spanning that timestamp.

### 5.5 Time as "September 2024"

**You**: Plot t2m for September 2024.

**Expected**:
- ✓ `find_time` resolves to nearest-match (e.g. 2024-09-01) and
  records `time_match: "nearest"`.

### 5.6 Time as "first"/"last"

**You**: Plot t2m for the first time step.

**Expected**:
- ✓ `find_time` returns `time_index: 0`.
- ✓ Plot title includes the actual ISO timestamp.

### 5.7 Out-of-range time

**You**: Plot t2m for 1850-01-01 (in a file covering 2024 only).

**Expected**:
- ✓ Either `ambiguous` time_match with "no nearby match in file
  coverage" prompt, OR clearly-flagged nearest match (first time
  step) with a warning.

---

## 6. Plot maps — rectilinear

### 6.1 Basic plot

**You**: Plot t2m for the latest time.

**Expected**:
- ✓ Tools called: inspect (cached if available) →
  resolve_spec → read_slice → render_map.
- ✓ `render_map` returns `output_path` under `.metplot/plots/`.
- ✓ PNG > 10 KB.
- ✓ `oracle.drawn.projection_class = "PlateCarree"` by default.
- ✓ Coastlines drawn.
- ✓ Colorbar present (cmap = `RdYlBu_r` for temperature).

### 6.2 Custom output path

**You**: Save the plot to `/tmp/my_plot.png`.

**Expected**:
- ✓ File written exactly at `/tmp/my_plot.png`.
- ✓ Atomic-rename semantics (no half-written file on crash).

### 6.3 Explicit projection

**You**: Same plot but Robinson projection.

**Expected**:
- ✓ `oracle.drawn.projection_class = "Robinson"`.

### 6.4 Explicit colormap

**You**: Use the viridis colormap.

**Expected**:
- ✓ Colormap is viridis, not the field-character default.
- ✓ `oracle.style_resolution_sources.colormap = "explicit"`.

### 6.5 Unknown colormap

**You**: Use the `blurple` colormap.

**Expected**:
- ✓ `ambiguous` envelope, subcode `unknown_colormap`.
- ✓ `candidates` lists `viridis` and `RdBu_r`.

### 6.6 vmin/vmax

**You**: Plot t2m with vmin=200, vmax=320.

**Expected**:
- ✓ `oracle.data.vmin_used = 200.0`, `vmax_used = 320.0`.
- ✓ Out-of-range cells render in the colormap's `set_under` /
  `set_over` colors.

### 6.7 Percentile clip

**You**: Plot the data clipped to the 2nd–98th percentile.

**Expected**:
- ✓ `oracle.safety_actions.applied_clip_pct = [2, 98]`.
- ✓ vmin/vmax in the result match the empirical percentiles.

### 6.8 Auto-downsample on huge grids

**You**: Plot t2m on a 4320×8640 grid (hypothetical 4-km global).

**Expected**:
- ✓ Renderer auto-downsamples per cycle-2 spec §6.
- ✓ `oracle.safety_actions.applied_downsample` populated with
  the downsample action object.
- ✓ Warning `AUTO_DOWNSAMPLED` in the envelope.

### 6.9 Constant field

**You**: Plot a field where every cell has the same value.

**Expected**:
- ✓ Warning `CONSTANT_FIELD` in the envelope.
- ✓ Plot still produced (single-color map).

### 6.10 All-NaN field

**You**: Plot a field where every cell is NaN.

**Expected**:
- ✓ `ambiguous` envelope, subcode `all_nan`.
- ✓ Agent surfaces and asks for a different time/region.

---

## 7. Plot maps — curvilinear (WRF, ROMS)

### 7.1 WRF T2 map

**Setup**: a WRF history file.

**You**: Plot T2 for the first output time.

**Expected**:
- ✓ Inspect → `convention.primary = "WRF"`,
  `spatial.coord_kind = "curvilinear"`.
- ✓ Renderer uses pcolormesh with curvilinear 2-D XLAT/XLONG —
  no regrid step needed for T2 (scalar grid).

### 7.2 WRF U-component map (staggered → centers)

**You**: Plot U at the lowest model level.

**Expected**:
- ✓ Agent calls `regrid_to_centers` BEFORE render_map (U is on
  `west_east_stag`).
- ✓ Output is rendered at mass-point centers.
- ✓ Reported in the chat: "regridded U from west_east_stag to
  centers via regrid_to_centers".

### 7.3 ROMS temp at surface

**Setup**: a ROMS history file.

**You**: Plot ROMS temperature at the surface.

**Expected**:
- ✓ Inspect detects ROMS, `vertical.kind = "sigma"`.
- ✓ Surface = top sigma layer (`s_rho=-1` or `s_rho=0`
  depending on the file's stretching profile).

### 7.4 ROMS at specific sigma

**You**: Plot ROMS temp at sigma=-0.5.

**Expected**:
- ✓ `resolve_spec` parses `level` as a numeric sigma value,
  finds the nearest s_rho index.

---

## 8. Plot maps — unstructured (MPAS family)

### 8.1 Paired-MPAS surface temp plot

**Setup**: history + mesh on disk.

**You**: Map the MPAS Temperature at the surface for the first
time step, using `ocean_mesh.nc` as the mesh.

**Expected**:
- ✓ Pipeline: inspect(history, mesh_path=mesh) →
  read_slice(history, Temperature, time=first, level=0,
  mesh_path=mesh) → render_map(values, mesh_path).
- ✓ render_map dispatches to `_render_unstructured_map` (the
  cycle-8 branch).
- ✓ Uses `uxarray.open_grid(mesh_path)` + `uxgrid.to_polycollection()`.
- ✓ PNG > 100 KB.
- ✓ `oracle.drawn.grid_kind = "unstructured"`.
- ✓ `oracle.drawn.n_cells = 7153`.
- ✓ `oracle.drawn.mesh_path = "/data/ocean_mesh.nc"`.

### 8.2 MPAS plot without supplying mesh (error path)

**You**: Map MPAS Temperature from
`ocn.hist.0001-02-01_00.00.00.nc`. (no mesh hint)

**Expected**:
- ✓ Inspect step returns ambiguous mesh_pairing_required.
- ✓ Agent surfaces candidate mesh files and asks the user to
  pick one before plotting.

### 8.3 MPAS plot with wrong mesh

**Setup**: a history with `NCells=7153` and a mesh with
`nCells=5000` (mismatched).

**You**: Plot Temperature using the mismatched mesh.

**Expected**:
- ✓ Envelope: `ok=false`,
  `error.code = "multi_file_combine_failed"`.
- ✓ Error message names the mismatch: `cell-dim size mismatch:
  history.NCells=7153, mesh.nCells=5000`.

### 8.4 MPAS plot with Robinson projection

**You**: Plot MPAS Temperature with Robinson projection.

**Expected**:
- ✓ Same as 8.1 but `oracle.drawn.projection_class = "Robinson"`.
- ✓ Visually: round-pole global map.

### 8.5 MPAS lat/lon already in degrees

**Setup**: a synthetic mesh where `latCell`/`lonCell` are in
degrees (NOT radians).

**You**: Plot Temperature.

**Expected**:
- ✓ Radian-vs-degree detection sees |max| > 2π and skips
  conversion.
- ✓ Map renders at the correct coordinates (no flat-strip
  collapse).

---

## 9. Mesh-pairing flow

### 9.1 Pairing heuristic — exact-prefix match

**Setup**: `myrun.hist.2024-01.nc` and `myrun_mesh.nc` in the
same dir.

**You**: Inspect `myrun.hist.2024-01.nc`.

**Expected**:
- ✓ Ambiguous envelope.
- ✓ `candidates[0].value` ends in `myrun_mesh.nc` (rank 1 = exact
  prefix).

### 9.2 Pairing heuristic — init.nc

**Setup**: `out.0001-01.nc` and `init.nc` in the same dir.

**You**: Inspect `out.0001-01.nc`.

**Expected**:
- ✓ `init.nc` appears in candidates.

### 9.3 Pairing heuristic — broad mesh match

**Setup**: `ocn.hist.*.nc` (no shared prefix with any mesh
file) and `ocean_mesh.nc` in the same dir.

**You**: Inspect `ocn.hist.*.nc`.

**Expected**:
- ✓ `ocean_mesh.nc` appears in candidates via the broad
  `*_mesh.nc` heuristic.

### 9.4 Pairing self-exclusion

**Setup**: `my_mesh.nc` alone in a dir.

**You**: Inspect `my_mesh.nc`.

**Expected**:
- ✓ `inspect` reports it as a valid mesh file (ok=true).
- ✓ `find_mesh_candidates` (if called) returns `[]` — the file
  doesn't list itself as its own pair.

### 9.5 Explicit override of suggested mesh

**Setup**: history with two plausible mesh candidates.

**You**: Inspect history using `/another/mesh.nc` (not the
top suggestion).

**Expected**:
- ✓ Agent honors the explicit `mesh_path`.
- ✓ Validates dim-match.

---

## 10. Time-series plots

### 10.1 Global-mean time series

**You**: Plot the global-mean t2m time series for 2024.

**Expected**:
- ✓ Skill: `netcdf-plot-timeseries`.
- ✓ Pipeline: compute_stats(area-weighted mean) along time →
  render_timeseries.
- ✓ Y axis labeled with units (K or °C after conversion).
- ✓ X axis is dates.

### 10.2 Single-point time series

**You**: Plot the t2m time series at lat=40, lon=-74.

**Expected**:
- ✓ Nearest grid cell selected.
- ✓ Single trace plotted.

### 10.3 Multi-region overlay

**You**: Plot the t2m time series for North Atlantic vs.
Tropical Pacific.

**Expected**:
- ✓ Two traces, two labels, one legend.
- ✓ Both regions resolved via regions.json.

---

## 11. Vertical profile plots

### 11.1 Pressure profile

**You**: Plot the t profile at lat=0, lon=180 for 2024-09-15.

**Expected**:
- ✓ Skill: `netcdf-plot-profile`.
- ✓ Y axis: pressure, INVERTED (high pressure at the bottom).
- ✓ X axis: temperature.

### 11.2 Height profile

**You**: Plot the salinity profile at lat=30, lon=-65 (height
axis).

**Expected**:
- ✓ Y axis: depth/altitude, NOT inverted.

### 11.3 Cross-section

**You**: Plot a north-south temperature cross-section along
lon=0.

**Expected**:
- ✓ 2-D output: latitude (x) vs. vertical (y).
- ✓ Pressure inverted if applicable.

---

## 12. Regions & longitude convention

### 12.1 Named region

**You**: Plot t2m over the North Atlantic.

**Expected**:
- ✓ Agent looks up "North Atlantic" in regions.json.
- ✓ bbox applied.
- ✓ Plot extent matches the named region.

### 12.2 Custom bbox

**You**: Plot t2m over [20, -80, 60, 0] (lat_min, lon_min,
lat_max, lon_max).

**Expected**:
- ✓ bbox honored.
- ✓ No region.json lookup.

### 12.3 Cross-dateline region

**You**: Plot t2m over [(-20, 170), (20, -170)] (Pacific
cross-dateline).

**Expected**:
- ✓ Renderer handles the dateline wrap.
- ✓ Output map shows both sides.

### 12.4 Region in `-180..180`, file in `0..360`

**Setup**: file with lon in [0, 360).

**You**: Plot over the North Atlantic (which crosses 0 in
`-180..180`).

**Expected**:
- ✓ Renderer auto-shifts.
- ✓ Warning `LON_SHIFT_APPLIED` in the envelope.

### 12.5 Region clip on MPAS (cycle 9+)

**You**: Plot MPAS Temperature over the North Atlantic.

**Expected**:
- ✓ Agent surfaces: region clipping not supported on unstructured
  meshes in cycle 8; plot is global.

---

## 13. Vertical level selection

### 13.1 Pressure in hPa

**You**: Plot t at 500 hPa.

**Expected**:
- ✓ `level=500` resolved to nearest plev index.

### 13.2 Surface sentinel

**You**: Plot t at the surface.

**Expected**:
- ✓ For pressure axis: highest pressure (bottom of atmosphere).
- ✓ For depth axis: 0 (top of ocean).
- ✓ For ROMS sigma: top layer.
- ✓ For MPAS NVertLayers: layer 0.

### 13.3 Level value with non-default units

**You**: Plot t at altitude 5000.

**Expected**:
- ✓ Numeric value 5000 mapped to nearest index in the altitude
  coord.

### 13.4 No vertical dim (variable is 3-D)

**You**: Plot t2m at level=0. (file has no vertical dim)

**Expected**:
- ✓ Either: agent ignores level (variable doesn't need one), OR
  envelope `error.code = "not_4d"` if the user explicitly demanded
  a level.

---

## 14. Multi-file glob (time-concat)

### 14.1 Monthly CMIP files

**Setup**: `/data/era5_t2m_2024-{01,02,03,...,12}.nc`.

**You**: Inspect `/data/era5_t2m_2024-*.nc`.

**Expected**:
- ✓ `result.kind = "local_multi"`.
- ✓ `result.files` sorted (12 files).
- ✓ Time range spans all months concatenated.

### 14.2 Plot from glob

**You**: Plot the September 2024 t2m from those files.

**Expected**:
- ✓ Renderer correctly selects from the right month's file.

### 14.3 Glob with mesh (unstructured)

**You**: Plot MPAS Temperature from `/data/ocn.hist.*.nc` using
`ocean_mesh.nc`.

**Expected**:
- ✓ Currently: NOT supported in cycle 8. Agent surfaces "multi-file
  unstructured time-concat is cycle 9+ scope".

### 14.4 Mixed conventions in a glob

**Setup**: glob includes one CMIP file and one WRF file
(accidentally).

**You**: Inspect the glob.

**Expected**:
- ✓ Envelope: `ambiguous`, subcode `multi_file_combine`.
- ✓ Candidates list the two competing conventions.

---

## 15. Style by reference

### 15.1 Attach a reference image, ask for a map

**Setup**: a reference PNG of a published figure with a clear
visual style (Robinson projection, RdBu_r colormap, gridlines,
top-positioned colorbar).

**You**: Make a map of t2m with the same style as this. *[attaches
the image]*

**Expected**:
- ✓ Agent loads `docs/style_template_extraction_prompt.md`.
- ✓ Vision model extracts JSON `style_template` with
  `projection`, `colormap`, `gridlines`, `colorbar_position`,
  `confidence`.
- ✓ `style_template` passed through to `render_map`.
- ✓ Output PNG visually matches the reference style.
- ✓ `oracle.style_template_applied` block records the
  reference image path + confidence.

### 15.2 Explicit override beats template

**You**: Use this reference style, but with viridis colormap.

**Expected**:
- ✓ Template-extracted colormap overridden by explicit viridis.
- ✓ `oracle.style_resolution_sources.colormap = "explicit"`.

### 15.3 Low-confidence template

**Setup**: a blurry / ambiguous reference image.

**You**: Make a map with this style.

**Expected**:
- ✓ Template `confidence < 0.5`.
- ✓ Agent surfaces the low confidence and asks the user to
  confirm or override.

---

## 16. Remote files (HTTPS, SSH)

### 16.1 HTTPS URL

**You**: Inspect
`https://noaa.gov/data/cmip6/tas_Amon_*.nc`.

**Expected**:
- ✓ Inspect works (NetCDF-via-HTTP if the server supports byte-range).
- ✓ `result.kind = "remote_url"`.
- ✓ Slow opens (> 30s) emit a `SLOW_REMOTE_READ` warning.

### 16.2 SSH path (no auth set up)

**You**: Inspect `ssh://hpc.example.org:/data/run.nc`.

**Expected**:
- ✓ Envelope: `ambiguous`, subcode `ssh_auth_needed`.
- ✓ Candidates: identity_file, password, ssh_config_alias.
- ✓ Agent prompts the user.

### 16.3 SSH with identity file

**You**: Inspect that SSH file using `~/.ssh/id_ed25519`.

**Expected**:
- ✓ Inspect succeeds via SSH + paramiko.
- ✓ `ssh_config` retry param honored.

### 16.4 SSH auth failure

**You**: Inspect with the wrong key.

**Expected**:
- ✓ Envelope: `ambiguous`, subcode `ssh_auth_needed`,
  `context.previous_error` populated, candidates re-prompt for
  a different method.

---

## 17. Skill-refiner loop

### 17.1 Correction logged

**Setup**: a session where the agent picked `sst` but the user
said "no, it's `tos`".

**Expected**:
- ✓ `.metplot/task-log.jsonl` has an `alias_correction` entry.
- ✓ Entry includes `input: "user said: SST"`,
  `resolved: "tos"`, `via: "user_correction"`.

### 17.2 End-of-session refinement (Claude Code Stop hook)

**Setup**: claude-code; task log has entries.

**You**: (end the session — say "thanks, that's all")

**Expected**:
- ✓ Stop hook fires.
- ✓ A new `claude -p '/metplot:refine'` subagent spawns in the
  background.
- ✓ Drafts produced in `.metplot/refinements/<timestamp>-*.md`.
- ✓ Original session's exit code is 0.

### 17.3 Manual /refine

**Setup**: any host except Claude Desktop / Codex.

**You**: `/refine` (or `/metplot:refine`).

**Expected**:
- ✓ `skill-refiner` reads `.metplot/task-log.jsonl`.
- ✓ Produces draft refinement files keyed on what was logged.

### 17.4 Refinement draft format

**Expected for an `add_alias` draft**:
- ✓ Markdown file under `.metplot/refinements/`.
- ✓ YAML frontmatter: `target`, `operation: add_alias`,
  `confidence`, `evidence: [...]`.
- ✓ Body: markdown table row(s) to splice into the target.

---

## 18. Refinement applier

### 18.1 List pending refinements

**You** (shell): `metplot-refine --list`.

**Expected**:
- ✓ Stdout shows each draft's filename, target, section,
  operation, confidence, evidence (multi-line).

### 18.2 Apply an `add_alias` interactively

**You**: `metplot-refine`.

**Expected**:
- ✓ Walks through each draft.
- ✓ Shows the proposed body.
- ✓ Prompts `[a]ccept / [s]kip / [r]eject / [q]uit`.
- ✓ On accept: splices body between `<!-- REFINER_INSERT_BELOW -->`
  and `<!-- REFINER_INSERT_ABOVE -->` markers in `aliases.md`.
- ✓ Moves applied draft to `.metplot/refinements/applied/<timestamp>-…`.

### 18.3 Apply a `replace_section`

**Expected**:
- ✓ The named `## SectionName` body is replaced.
- ✓ Header line preserved.
- ✓ Other sections untouched.

### 18.4 Apply a `set_config_default`

**Expected**:
- ✓ YAML frontmatter of the target SKILL.md gets the new key.
- ✓ Existing keys preserved.
- ✓ Body preserved verbatim.
- ✓ New frontmatter parses cleanly via yaml.safe_load.

### 18.5 `add_region` is stubbed

**You**: (a draft refinement with operation: add_region)

**Expected**:
- ✓ Applier raises `ClickException` with message naming the
  deferral reason ("cycle-6 Phase A surfaced zero region
  findings; stays stubbed until a future cycle's Phase A
  justifies").

### 18.6 Refusing a malformed target

**You**: (a draft pointing at a SKILL.md with no `## Pitfalls`
section, op = `replace_section`)

**Expected**:
- ✓ ClickException with actionable repro info.
- ✓ Target file UNCHANGED.

### 18.7 Atomic write

**Setup**: kill the applier mid-write somehow.

**Expected**:
- ✓ No `<target>.tmp` leftover.
- ✓ Target file is either fully old or fully new — never
  half-written.

---

## 19. Uninstall + clean reinstall

### 19.1 Claude Code uninstall + reinstall

**You** (in Claude Code): `/plugin uninstall metplot`,
`/plugin marketplace remove metplot-local`, then in shell:
`pip uninstall metplot-netcdf-reader metplot-plot-renderer`,
then `rm -rf ~/.claude/plugins/cache/metplot-local`.

**Expected**:
- ✓ After restart, `/metplot:setup` no longer in autocomplete.
- ✓ `which metplot-netcdf-reader` returns nothing.
- ✓ `/plugin list` doesn't show metplot.

**You**: Reinstall per §1.1.

**Expected**:
- ✓ Fresh install works end-to-end. No "version conflict" or
  "already installed" errors.

### 19.2 Workspace state cleanup

**You** (shell): `rm -rf .metplot`.

**Expected**:
- ✓ Next inspect goes cold (no cached envelope).
- ✓ Next session writes a fresh task-log.

### 19.3 Reinstall over older version

**Setup**: an older metplot install on disk.

**You**: Run the install steps per §1 without uninstalling first.

**Expected**:
- ✓ Pip resolver may complain about conflicting versions.
- ✓ Documented behavior: uninstall first per §19.1, then
  reinstall.

---

## 20. Failure modes & error envelopes

These are the error / ambiguous envelopes the agent must
surface gracefully. None of these should crash; all should
produce structured output the agent can act on.

### 20.1 `file_not_found`

**You**: Inspect `/does/not/exist.nc`.

**Expected**: `ok=false`, `error.code = "file_not_found"`.

### 20.2 `unsupported_path_scheme`

**You**: Inspect `ftp://example.org/file.nc`.

**Expected**: `error.code = "unsupported_path_scheme"`.

### 20.3 `ambiguous` / `convention`

**Setup**: a file that could plausibly be CF or WRF.

**Expected**: `ambiguous`, subcode `convention`, candidates list.

### 20.4 `ambiguous` / `variable`

(Covered in §5.3.)

### 20.5 `ambiguous` / `ssh_auth_needed`

(Covered in §16.2.)

### 20.6 `ambiguous` / `mesh_pairing_required`

(Covered in §3.6 / §3.7 / §9.)

### 20.7 `ambiguous` / `empty_slice`

(Covered in §6.10 / §4.5.)

### 20.8 `ambiguous` / `all_nan`

(Covered in §6.10.)

### 20.9 `multi_file_combine_failed`

**You**: Plot using a mismatched history/mesh pair.

**Expected**: `error.code = "multi_file_combine_failed"` with
the mismatched-dim names + sizes in the message.

### 20.10 `not_4d`

**You**: Ask for a level on a variable with no vertical dim.

**Expected**: `error.code = "not_4d"`.

### 20.11 `cartopy_missing`

(Covered in §2.3.)

### 20.12 `internal_render_error`

**Setup**: pass a render spec that triggers a renderer bug.

**Expected**: `error.code = "internal_render_error"`,
`message: "<ExceptionClass>: <message>"`. Should NEVER propagate
a raw Python traceback unbounded.

### 20.13 Warnings (not errors)

These should appear in `result.warnings` but the envelope is
still `ok=true`:

- `LON_SHIFT_APPLIED` — coordinate convention shift fired
- `AUTO_DOWNSAMPLED` — grid too big for the figure size
- `PERCENTILE_CLIP_APPLIED` — vmin/vmax derived from clip
- `HIGH_NAN_FRACTION` — > 50 % of cells are NaN
- `CONSTANT_FIELD` — zero variance
- `NON_MONOTONIC_COORD` — lat/lon/time not monotonic
- `NON_STANDARD_CALENDAR` — calendar isn't gregorian/standard
- `SLOW_REMOTE_READ` — open took > 30 s
- `TIME_DECODE_FAILED` — Time dim present but no time coord
  (cycle 6 task 3 step 1; MPAS mesh files)

---

## 21. Real-data scenarios (`data/omega/`, `data/e3sm/`)

The repository bundles two small real-model dataset folders so
the tester (and the dogfood-tester guide) can exercise the
agent against actual MPAS-Ocean (Omega) and E3SM outputs
without needing to download anything. These tests are the
ground truth for cycle-9 through cycle-12 capabilities.

### 21.0 What's in `data/`

**`data/omega/`** — MPAS-Ocean / E3SM Omega ocean component.

| File | Shape / role |
|---|---|
| `ocn.hist.0001-{02..12}-01_00.00.00.nc`, `ocn.hist.0002-01-01_00.00.00.nc` | 12 monthly history files (Feb 0001 → Jan 0002). Each: `(time=1, NCells=7153, NVertLayers=60)`. Vars: `Temperature`, `Salinity`, `LayerThickness`, `SshCell`, `NormalVelocity`, `Debug{1,2,3}`. Time encoded as `seconds since 0001-01-01 00:00:00` (noleap-ish year-0001). |
| `ocn.hifreq.0001-06.nc`, `ocn.hifreq.0001-07.nc` | Sub-monthly cadence (4 + 3 timesteps respectively). Vars: `Temperature`, `Salinity`, `Debug{1,2,3}`. Useful for fine-grained timeline tests. |
| `ocn.restart.0001-07-01_00.00.00.nc`, `ocn.restart.0002-01-01_00.00.00.nc` | Full-state restart files (much larger). |
| `ocean_test_mesh.nc` | MPAS mesh (`nCells=7153`, `nVertLevels=60`, includes `latCell`/`lonCell` in radians and `areaCell`). Pair with any `ocn.hist.*.nc`. |
| `global_test_mesh.nc`, `planar_test_mesh.nc` | Alternative meshes (global lat/lon and planar Cartesian). |
| `IOTest.nc` | I/O smoke fixture. |

**`data/e3sm/`** — E3SM component outputs (CICE / SCREAM / ELM / CPL).

| File | Shape / role |
|---|---|
| `cice.r.0001-01-01-21600.nc` | CICE5/6 restart. `(ncat=1, nj=1, ni=48602)` flattened block-decomposed. Vars: `aicen`, `vicen`, `vsnon`, `Tsfcn`. Needs a paired CICE grid file for plotting. |
| `scream.phys.h.INSTANT.nsteps_x22.0001-01-01-39600.nc` | SCREAM (EAMxx) physics history. `(time=1, ncol=48602, lev=128)`. Vars: `T_mid`, `horiz_winds`, `pseudo_density`, `p_mid`, `area`. EAMxx physics-column grid. |
| `scream.phys.h.rhist.INSTANT.nsteps_x22.0001-01-01-21600.nc` | SCREAM rhist (post-restart history). Exercises the cycle-10 time-decode fallback. |
| `scream.diags.h.{,rhist.}INSTANT.nsteps_x22.0001-01-01-*.nc` | SCREAM diagnostic history. Same grid as `phys.h`. |
| `scream.r.INSTANT.nsteps_x12.0001-01-01-21600.nc` | SCREAM restart. |
| `elm.r.0001-01-01-21600.nc` | E3SM Land Model restart. Many unstructured land-grid dims (`gridcell=15865`, `column=238788`, `pft=492628`, levels like `levgrnd`, `levsno`). Detect-only (cycle 10). |
| `elm.rh0.0001-01-01-21600.nc` | ELM secondary restart history. |
| `cpl.hi.0001-01-01-39600.nc` | E3SM coupler history. `(time=1)` with multiple `doma_*` / `doml_*` / `domo_*` / `domi_*` domain prefixes. Detect-only (cycle 10). |
| `cpl.r.0001-01-01-21600.nc` | CPL restart. |

These prompts assume the working directory is the repo root so
relative paths work. Replace with absolute paths if the agent
needs them.

### 21.1 Inspect — Omega monthly history (paired mesh)

**You**: Inspect `data/omega/ocn.hist.0001-02-01_00.00.00.nc`
using `data/omega/ocean_test_mesh.nc` as the mesh.

**Expected**:
- ✓ Single `inspect(path, mesh_path)` call.
- ✓ `result.convention = "MPAS"`, `result.spatial.coord_kind =
  "unstructured"`, `result.spatial.n_cells = 7153`.
- ✓ `result.spatial.lon_convention = "0..360"` (MPAS radians
  decoded to degrees).
- ✓ `result.time.n = 1`, range starts `0001-02-01`.
- ✓ Variables include `Temperature`, `Salinity`, `SshCell`
  tagged `grid_kind: "cell_centered"`.

### 21.2 Inspect — Omega monthly glob (12 files + mesh)

**You**: Inspect `data/omega/ocn.hist.000*-*-01_00.00.00.nc` with
mesh `data/omega/ocean_test_mesh.nc`.

**Expected**:
- ✓ `kind = "local_multi"`, `len(result.files) = 13` (12 monthly
  histories + 1 mesh in the list).
- ✓ `time.n = 12`, range Feb 0001 → Jan 0002.
- ✓ Variables enumerate once (de-duplicated across files).
- ✓ `spatial.coord_kind = "unstructured"`, `n_cells = 7153`.
- ✓ No `mesh_pairing_required` ambiguity (mesh supplied
  explicitly).

### 21.3 Inspect — Omega hifreq (sub-monthly)

**You**: Inspect `data/omega/ocn.hifreq.0001-06.nc` paired with
the mesh.

**Expected**:
- ✓ `time.n = 4` (4 timesteps within June 0001).
- ✓ Time axis monotonic; frequency irregular but reported.
- ✓ Variables: `Temperature`, `Salinity`, `Debug{1,2,3}` —
  smaller set than the monthly histories.

### 21.4 Time-series — single cell over 12 months

**You**: Plot a time series of Omega `Temperature` at the
surface for cell index 100 over all 12 monthly files in
`data/omega/`, using `ocean_test_mesh.nc`.

**Expected**:
- ✓ Pipeline: paired-glob `inspect` → `read_slice(glob,
  "Temperature", level=0, cell_index=100, mesh_path=...,
  time="all")` → result shape `[12]` → `render_timeseries`.
- ✓ PNG > 5 KB with 12 points on the time axis, dates spanning
  Feb 0001 → Jan 0002.
- ✓ Y-axis label includes units (e.g. `degree_C`).
- ✓ Series is finite (no all-NaN warning).

### 21.5 Time-series — North Atlantic regional mean

**You**: Plot the area-weighted mean Omega `Temperature` over
the North Atlantic (lon 280..360, lat 20..70) at the surface
across the 12 monthly files.

**Expected**:
- ✓ Calls `cells_in_bbox(mesh, lat_min=20, lat_max=70,
  lon_min=280, lon_max=360)` — note the 0..360 lon convention
  (NA is 280..360, **not** −80..0).
- ✓ `read_slice(glob, "Temperature", level=0,
  cell_indices=[...], mesh_path=..., time="all")` → shape
  `[12, ~470]`.
- ✓ Skill-side area-weighted mean via `area_weights(mesh_ds,
  indices=...)` → shape `[12]`.
- ✓ `render_timeseries` → PNG with title naming the region and
  the weighting method.

### 21.6 Time-series — global area-weighted mean

**You**: Plot the global area-weighted mean of Omega
`Temperature` at the surface over the 12 monthly files.

**Expected**:
- ✓ No `cells_in_bbox` call (global = all cells).
- ✓ `area_weights(mesh_ds)` returns shape `[7153]`.
- ✓ Skill-side weighted mean → shape `[12]`.
- ✓ Render → PNG with single trace, no legend (single series).

### 21.7 Time-series — sub-monthly cadence (hifreq glob)

**You**: Plot the time series of `Temperature` at cell 100,
surface, across `data/omega/ocn.hifreq.0001-*.nc` (both June
and July files), using `ocean_test_mesh.nc`.

**Expected**:
- ✓ Paired-glob inspect of 2 hifreq files → `time.n = 7` (4
  June + 3 July).
- ✓ `read_slice(glob, "Temperature", level=0, cell_index=100,
  mesh_path=...)` → shape `[7]`.
- ✓ Render → PNG with 7 time points spread irregularly across
  June–July of year 0001.
- ✓ X-axis tick labels reflect the actual irregular cadence
  (not pretend-monthly).

### 21.8 Vertical profile — single cell, all 60 levels

**You**: Plot the vertical Temperature profile at cell index
100 from `data/omega/ocn.hist.0001-02-01_00.00.00.nc`, paired
with the mesh.

**Expected**:
- ✓ `read_slice(history, "Temperature", time="first",
  cell_index=100, mesh_path=...)` → shape `[60]` (all
  `NVertLayers`).
- ✓ `render_profile` → PNG with y-axis label "depth" or "layer
  index", y-axis **inverted** (surface at top, deep at bottom
  for MPAS-Ocean convention).
- ✓ Variable label "Temperature" on x-axis with units.

### 21.9 Vertical profile — by lat/lon (find_nearest_cell)

**You**: Plot the Temperature profile at lat=30, lon=300 from
the same Omega history.

**Expected**:
- ✓ Calls `find_nearest_cell(mesh, lat=30, lon=300)` → integer
  index.
- ✓ Reports the chosen cell index back to the user (e.g.
  "nearest cell: 4217").
- ✓ Then runs the §21.8 pipeline with that index. PNG looks
  similar.
- ✓ Lon must be in the mesh's 0..360 convention (don't say
  −60).

### 21.10 Map — paired mesh on real data

**You**: Map Omega `Temperature` at the surface for the first
time step from `data/omega/ocn.hist.0001-02-01_00.00.00.nc`,
using `ocean_test_mesh.nc`.

**Expected**:
- ✓ Pipeline: paired `inspect` → `read_slice(history,
  "Temperature", time="first", level=0, mesh_path=mesh)` →
  `render_map(...)`.
- ✓ `oracle.drawn.grid_kind = "unstructured"`,
  `n_cells = 7153`, `mesh_path` echoed.
- ✓ PNG > 100 KB, full globe in default projection.

### 21.11 Hyperslab — every other timestep (cycle 12)

**You**: Read every other timestep of `Temperature` from
`data/omega/ocn.hifreq.0001-06.nc` (i.e. timesteps 0 and 2).

**Expected**:
- ✓ Calls `read_slice(path, "Temperature",
  index_selectors={"time": [0, 3, 2]}, mesh_path=mesh)`.
- ✓ `result.shape = [2, 60, 7153]` (or with mesh-path skipped:
  `[2, 60, 7153]`).
- ✓ Stop is inclusive (`[0, 3, 2]` → indices 0, 2 → 2 elements,
  not 1).

### 21.12 Hyperslab — top-of-water-column subset

**You**: Read `Temperature` from
`data/omega/ocn.hist.0001-02-01_00.00.00.nc` for the top 10
vertical layers only.

**Expected**:
- ✓ Calls `read_slice(path, "Temperature", time="first",
  index_selectors={"NVertLayers": [0, 9]})` → shape `[7153,
  10]` (NCells dim comes first in this file's on-disk order,
  NVertLayers second; cycle-3 read_slice preserves on-disk
  axis order).
- ✓ Dim name `NVertLayers` matched case-insensitively.

### 21.13 Reduce — global mean Temperature (collapse cells)

**You**: Compute the cell-averaged Temperature per (time,
level) from `data/omega/ocn.hist.0001-02-01_00.00.00.nc`.

**Expected**:
- ✓ Calls `reduce_variable(path, "Temperature",
  reduce_dims=["NCells"], op="avg")`.
- ✓ `result.shape = [1, 60]`, `result.dims = ["time",
  "NVertLayers"]`, `result.reduced_dims = ["NCells"]`.
- ✓ Result is a scalar profile (one value per level).
- ✓ Caveat: this is **unweighted**; if the user wants
  area-weighting, route them to the skill-side
  `area_weights(...)` pattern (cycle 11).

### 21.14 Reduce — time average over the 12-month series

**You**: Compute the annual-mean Temperature at the surface
from the 12 Omega monthly files.

**Expected**:
- ✓ Pipeline: paired-glob inspect → `reduce_variable(glob,
  "Temperature", reduce_dims=["time"], op="avg",
  mesh_path=mesh)` → shape `[7153, 60]` (NCells dim is
  before NVertLayers in this file's on-disk order; reducing
  time leaves the remaining two dims in that order).
- ✓ Or: agent first uses `index_selectors={NVertLayers: [0,
  0]}` + reduce over time → shape `[7153]`.

### 21.15 dump_cdl — header-only schema

**You**: Dump the CDL header (no data) of
`data/omega/ocean_test_mesh.nc`.

**Expected**:
- ✓ Calls `dump_cdl(path, header_only=True)`.
- ✓ Returns a multi-line CDL string starting `netcdf
  ocean_test_mesh {` and containing `dimensions:` + `nCells = 7153
  ;` + `variables:` + a `// global attributes:` block.
- ✓ Does NOT contain a `data:` section.

### 21.16 dump_cdl — variables filter

**You**: Show me just the `Temperature` variable schema from
`data/omega/ocn.hist.0001-02-01_00.00.00.nc`.

**Expected**:
- ✓ Calls `dump_cdl(path, variables=["Temperature"],
  header_only=True)`.
- ✓ The `variables:` block contains
  `double Temperature(time, NCells, NVertLayers) ;` and its
  attribute lines, but no other variable lines.

### 21.17 ncks side-by-side — hyperslab parity check

**You** (tester runs both):
```bash
ncks -O -v Temperature -d NCells,0,99 \
     data/omega/ocn.hist.0001-02-01_00.00.00.nc /tmp/ncks_out.nc
```
Then ask the agent: read Temperature from the same file with
`index_selectors={"NCells": [0, 99]}` and compare to
`/tmp/ncks_out.nc`.

**Expected**:
- ✓ Agent calls `read_slice(path, "Temperature",
  index_selectors={"NCells": [0, 99]}, max_inline_bytes=<big>)`.
- ✓ Returned values `np.array_equal` to the contents of
  `/tmp/ncks_out.nc` opened with xarray.
- ✓ Spec claim "bit-exact identical to `ncks -d`" holds end to
  end on real data.

### 21.18 ncwa side-by-side — reduction parity check

**You** (tester runs):
```bash
ncwa -O -v Temperature -y avg -a NCells \
     data/omega/ocn.hist.0001-02-01_00.00.00.nc /tmp/ncwa_out.nc
```
Then ask the agent to compute the cell-mean Temperature from
the same file.

**Expected**:
- ✓ Agent calls `reduce_variable(path, "Temperature",
  reduce_dims=["NCells"], op="avg")`.
- ✓ Returned array matches `/tmp/ncwa_out.nc` Temperature
  values within `rtol=1e-12` (numpy pairwise vs ncwa serial
  summation diverges at last ULPs — documented in cycle-12
  spec §1 success criterion #5).
- ✓ For `op="min"` or `op="max"`, the comparison is
  bit-exact (no accumulation).

### 21.19 CICE r-file detection (E3SM)

**You**: Inspect `data/e3sm/cice.r.0001-01-01-21600.nc`.

**Expected**:
- ✓ `ambiguous` envelope with `subcode =
  "mesh_pairing_required"` (cycle 9: CICE needs a separate
  grid file).
- ✓ `convention = "CICE"`, `cell_dim = "ni"`.
- ✓ Variable fingerprint detected: `aicen`, `vicen`, `Tsfcn`,
  `vsnon`.
- ✓ `error.candidates` lists likely sibling grid files; the
  bundled data doesn't include one, so the list may be empty
  — that's a valid "no candidate found" answer.

### 21.20 SCREAM (EAMxx) physics history detection

**You**: Inspect
`data/e3sm/scream.phys.h.INSTANT.nsteps_x22.0001-01-01-39600.nc`.

**Expected**:
- ✓ `ambiguous` envelope with `subcode =
  "mesh_pairing_required"`.
- ✓ `convention = "EAMxx"` (or `"SCREAM"`), takes precedence
  over plain CF via the `source` / `case` attrs / averaging
  attrs.
- ✓ `cell_dim = "ncol"`, `n_cells = 48602`.
- ✓ Variables include `T_mid`, `horiz_winds`, `p_mid` —
  `cell_centered`.

### 21.21 SCREAM rhist time-decode fallback (cycle 10)

**You**: Inspect
`data/e3sm/scream.phys.h.rhist.INSTANT.nsteps_x22.0001-01-01-21600.nc`.

**Expected**:
- ✓ No crash (cycle 10 fix: rhist files use an undecodable
  year-0001 origin under noleap; the adapter falls back to
  raw seconds).
- ✓ `result.warnings` contains `TIME_DECODE_FAILED` (or
  equivalent — surfacing the fallback path).
- ✓ Inspect otherwise succeeds and surfaces the schema as in
  §21.20.

### 21.22 ELM r-file detection (cycle 10)

**You**: Inspect `data/e3sm/elm.r.0001-01-01-21600.nc`.

**Expected**:
- ✓ `convention = "ELM"`.
- ✓ Surfaces the unstructured land-grid dims (`gridcell`,
  `column`, `pft`, `levgrnd`, `levsno`).
- ✓ Detection-only (cycle 10 scope): plotting is **not**
  shipped for ELM — the agent should respond with "I can see
  this is ELM, but plotting ELM grids is out of scope for the
  current release; routing to a non-plot action is fine".

### 21.23 CPL hi-file detection (cycle 10)

**You**: Inspect `data/e3sm/cpl.hi.0001-01-01-39600.nc`.

**Expected**:
- ✓ `convention = "CPL"` (E3SM coupler).
- ✓ Detection surfaces the `doma_*` / `doml_*` / `domo_*` /
  `domi_*` domain prefixes (atmosphere / land / ocean / ice).
- ✓ Detection-only (cycle 10 scope): same caveat as §21.22 —
  no plotting path shipped.

---

## Reporting failures

If any expected behavior fails, log a finding in
`docs/research/<YYYY-MM-DD>-test-findings.md` (or extend the
dogfood guide's findings file). Format:

```markdown
### <Short failure title>
- **Date**: <ISO>
- **Test reference**: §<N.M> of tester-guide.md
- **Files**: <which test files / synthetic fixtures>
- **Prompt**: <verbatim prompt that triggered the issue>
- **Expected**: <what should have happened>
- **Actual**: <what did happen, with error envelope or
  traceback>
- **Repro**: <minimal command/prompt sequence>
- **Severity**: blocker / major / minor / cosmetic
- **Suggested next step**: <fix / file upstream / scope to
  cycle N+>
```

Failures involving the inspect → slice → render pipeline are
high-priority. Failures involving cycle-9+ scope items
(EAMxx dycore, CICE flattened, region clip on unstructured) are
cosmetic / known — log them but don't block on them.

# Cycle 13 — Bundled follow-ons (4 themes)

> Spec for cycle 13. Bundles four standing follow-on themes
> from the cycle-11 §6 and cycle-12 §6 carry-over lists into a
> single multi-theme cycle. Single phase, TDD per theme.

## 0. Why this spec is shaped this way

After cycle 12 shipped, the standing backlog had four
distinct themes, each viable as its own cycle but each only
1-2 days of work after the cycle-11/12 plumbing landed. The
user opted to **bundle them as one cycle** to ship a coherent
"finish the unstructured story + close the detect-only gaps"
chapter.

| Theme | What | Builds on |
|---|---|---|
| A | CICE/EAMxx cell-axis selectors for `read_slice`, `find_nearest_cell`, `cells_in_bbox`, `area_weights` | Cycle 11 (MPAS `NCells` plumbing) |
| B | Map render for ELM (gridcell) and CPL (single domain) | Cycle 10 (detect-only); cycle 9 render-dispatcher pattern |
| C | Multi-cell overlay timeseries + named-region lookup on unstructured | Cycle 11 timeseries; existing `regions.json` |
| D | Cross-section plots (lat×depth / lon×depth / great-circle×depth) on unstructured | Cycle 11 cell-axis plumbing; new renderer entry |

Single-phase, no new third-party deps. Cycle 12 spec
explicitly listed all four themes as cycle-13+ candidates.

## 1. Scope and success criteria

### Phase shape: single-phase, theme-sequenced

Themes ship in order C → A → B → D (smallest first to build
momentum). One commit per theme; final commit for docs +
gate.

### Success criteria

Cycle 13 is successful when all of the following hold:

#### Theme C — overlay + named regions

1. **`find_region(name)` MCP helper** returns the bbox dict
   `{lat_min, lat_max, lon_min, lon_max, category, notes?}`
   for a name in `regions.json`. Case-insensitive on the
   name. Returns `ambiguous` envelope with close-match
   candidates when the name doesn't resolve.
2. **Cycle-11 `cells_in_bbox` accepts the lon_min/lon_max
   convention agnostically** — already does; this cycle adds
   a worked example in the timeseries SKILL.md showing the
   `find_region("North Atlantic")` → `cells_in_bbox(...)`
   pipeline with the lon-convention shift (NA `-80..0` →
   `280..360` for MPAS 0..360 meshes).
3. **Multi-cell overlay timeseries works end-to-end** — the
   timeseries skill ships a recipe for "compare 3 cells on
   one plot": loop `read_slice(..., cell_index=N)` over a
   list, build `series=[{values, time, label, color?}, ...]`,
   call `render_timeseries`. Existing renderer accepts
   multi-series unchanged.

#### Theme A — CICE/EAMxx selectors

4. **Cell-axis selectors generalized off MPAS-only** — the
   cycle-11 `find_nearest_cell` / `cells_in_bbox` /
   `area_weights` helpers accept a `convention` hint
   (`"MPAS" | "CICE" | "EAMxx" | "auto"`) and resolve the
   correct lat/lon variable + cell-dim name per family. For
   CICE: `TLAT` / `TLON` on `ni`. For EAMxx: `lat` / `lon`
   on `ncol`. Default `"auto"` sniffs from the mesh's
   variables.
5. **`read_slice(..., cell_index=N, cell_indices=[...])`**
   handles `ni` (CICE) and `ncol` (EAMxx) dims — currently
   only matches `ncells` case-insensitively. Cycle 13
   extends to the case-insensitive set `{ncells, ni, ncol}`.
6. **Synthetic-fixture-backed unit tests** for CICE +
   EAMxx selectors prove the helpers handle each family
   without an MPAS-only assumption.

#### Theme B — ELM/CPL map render

7. **`_render_elm_gridcell(spec)`** — new render dispatch
   for ELM. Reads `latixy`/`longxy` (or `lat`/`lon`
   fallback) at the `gridcell` dim. MVP: scatter plot
   (matplotlib `scatter`) of one variable at one timestep.
   PFT mosaic and column-level aggregation are explicitly
   out of scope.
8. **`_render_cpl_domain(spec)`** — new render dispatch for
   CPL. Reads one named domain (`doma_lat`/`doma_lon` /
   `doml_lat`/`doml_lon` / etc.) selected by user or
   defaulting to `doma_`. MVP: scatter of one variable on
   that domain. Multi-domain overlay is out of scope.
9. **`_peek_grid_kind` dispatcher extended** to recognize
   `elm` and `cpl` and route to the new helpers.

#### Theme D — cross-section

10. **`slice_along_section(mesh_path, lat1, lon1, lat2,
    lon2, n_samples)` MCP tool** — returns a dict with
    `cell_indices` (length `n_samples` integer array of the
    nearest cell at each sample point along the great
    circle), `distances_km` (length `n_samples` cumulative
    distance), and `coords` (length `n_samples` (lat, lon)
    pairs). Pure geometry; no data read.
11. **`render_section(spec)` plot-renderer tool** — new
    fourth renderer. Inputs: `values` (2-D, shape
    `[n_samples, n_levels]`), `distances_km` (length
    `n_samples`), `vertical_coord` (length `n_levels`),
    optional `title`, `units`, `cmap`. Output: PNG with
    distance on x, vertical on y (inverted for ocean
    convention), pcolormesh fill. Plot-renderer tool count
    3 → 4.
12. **End-to-end cross-section on real Omega data** —
    integration test that pairs Omega monthly + mesh,
    samples 100 points along a great circle, fetches
    Temperature at each cell across all 60 vertical layers,
    renders a cross-section PNG. Verifies the pipeline,
    not the absolute image content.

#### Gate

13. **`pytest -ra`**, **`ruff check`**, **`mypy src tools
    tests`** all green. ncks-parity tests still pass. No new
    mypy errors beyond the yaml-stub baseline. Total tool
    count: netcdf-reader 12 → 14 (`find_region`,
    `slice_along_section`); plot-renderer 3 → 4
    (`render_section`).

## 2. Out of scope this cycle

- **ELM PFT mosaic / landunit decomposition** — landgrid
  rendering at PFT or column granularity. Cycle 14+.
- **CPL multi-domain overlay** — rendering atm + lnd + ocn
  + ice domain points on one figure. Cycle 14+.
- **Cross-section interpolation modes** beyond
  nearest-cell-along-great-circle. Linear or area-weighted
  interpolation between cells: cycle 14+.
- **Cross-section time animation** (rotating through
  timesteps) — single timestep per render in cycle 13.
- **Render_section style-by-reference** — the cycle-3
  style-template path doesn't yet specify section-specific
  fields. Cycle 14+.
- **Multi-variable overlay** in one `read_slice` call (cycle
  12 §6 carry).
- **Per-record stride aggregation `ncks --mro`** (cycle 12
  §6 carry).
- **EAMxx dycore spectral-element grid** (still cycle 14+).
- **Region clipping on map renderer** (still deferred from
  cycle 9/10).

## 3. Affected surface

### 3.1 netcdf-reader — new tools

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/regions.py` (NEW) | `find_region(name)` lookup against `src/skills/netcdf-plot-map/references/regions.json`. Case-insensitive name match; ambiguous envelope on miss with close-match candidates. |
| `src/mcp/netcdf_reader/sections.py` (NEW) | `slice_along_section(mesh_ds, lat1, lon1, lat2, lon2, n_samples)` — pure-numpy great-circle sampler + nearest-cell lookup per sample. Reuses cycle-11 `find_nearest_cell` haversine internals. |
| `src/mcp/netcdf_reader/selectors_unstructured.py` | Extend `find_nearest_cell`, `cells_in_bbox`, `area_weights` to accept a `convention` hint and resolve the right lat/lon variable + dim name per family. Default `"auto"` sniffs the mesh. |
| `src/mcp/netcdf_reader/tools/resolve_spec.py` | Extend cell-dim recognition from `{ncells}` to `{ncells, ni, ncol}` (all case-insensitive). |
| `src/mcp/netcdf_reader/server.py` | Add `find_region` + `slice_along_section` to `list_tool_names()` and `dispatch()`. Count 12 → 14. |

### 3.2 plot-renderer — new render tool + ELM/CPL dispatches

| File | Change |
|---|---|
| `src/mcp/plot_renderer/tools/render_section.py` (NEW) | Fourth renderer. Accepts `(values, distances_km, vertical_coord)` + style fields. Pcolormesh fill, vertical-axis inverted by default for ocean convention. |
| `src/mcp/plot_renderer/tools/render_map.py` | Add `_render_elm_gridcell(spec)` + `_render_cpl_domain(spec)`. Extend `_peek_grid_kind` to detect `elm` (presence of `gridcell` dim + `latixy`/`longxy`) and `cpl` (presence of `doma_*`/`doml_*` vars). |
| `src/mcp/plot_renderer/server.py` | Add `render_section` to list_tool_names + dispatch. Count 3 → 4. |

### 3.3 Skills

| File | Change |
|---|---|
| `src/skills/netcdf-plot-timeseries/SKILL.md` | Add "Multi-cell overlay" subsection: `find_region` → `cells_in_bbox` → loop or pick → render with `series=[...]`. |
| `src/skills/netcdf-plot-map/SKILL.md` | Update unstructured branch: now covers MPAS + CICE + EAMxx + ELM + CPL families. Add "ELM gridcell scatter" + "CPL domain scatter" subsections. |
| `src/skills/netcdf-plot-profile/SKILL.md` | Add pointer to `render_section` as the related-but-different 2-D vertical visualization. |
| `src/skills/netcdf-plot-cross-section/SKILL.md` (NEW) | New short skill for cross-section requests. Routes "show me a lat×depth slice" / "lon×depth" / "great-circle from A to B" requests. |

### 3.4 Tests

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_regions.py` (NEW) | `find_region` happy + ambiguous + cross-dateline regions. |
| `tests/mcp/netcdf_reader/unit/test_sections.py` (NEW) | `slice_along_section` with synthetic mesh; distances; nearest-cell on great circle; degenerate (lat1==lat2, lon1==lon2). |
| `tests/mcp/netcdf_reader/unit/test_selectors_unstructured_generalized.py` (NEW) | Generalized `find_nearest_cell` + `cells_in_bbox` + `area_weights` against CICE-shape and EAMxx-shape synthetic meshes. |
| `tests/mcp/netcdf_reader/unit/test_read_slice_ni_ncol.py` (NEW) | `read_slice(..., cell_index=N)` against `ni`-dim and `ncol`-dim variables. |
| `tests/mcp/plot_renderer/unit/test_render_section.py` (NEW) | Synthetic 2-D + axis → PNG + oracle. |
| `tests/mcp/plot_renderer/unit/test_render_elm.py` (NEW) | Synthetic ELM-shaped grid → scatter PNG. |
| `tests/mcp/plot_renderer/unit/test_render_cpl.py` (NEW) | Synthetic CPL-shaped grid → scatter PNG. |
| `tests/mcp/netcdf_reader/integration/test_real_omega_section.py` (NEW) | End-to-end great-circle cross-section through Omega data. |
| `tests/mcp/netcdf_reader/unit/test_server.py` | Update tool count 12 → 14. |
| `tests/mcp/plot_renderer/unit/test_server.py` | Update tool count 3 → 4. |
| `tests/targets/claude_code/test_mcp_smoke.py` | Bundle counts: netcdf 12 → 14; renderer 3 → 4. |

### 3.5 Documentation

| File | Change |
|---|---|
| `README.md` | Capability rows: "Multi-cell overlay + named regions"; "ELM/CPL map render (gridcell-level)"; "Cross-section plots on unstructured". |

## 4. Cross-cutting principles

1. **TDD per theme.** One commit per theme, tests-first.
2. **No new third-party deps.** Great-circle math is numpy
   haversine + linear-interp samples.
3. **Sniff don't ask.** Selector helpers default to `"auto"`
   convention — sniff the mesh's variable names.
4. **MVP renderers.** ELM/CPL scatter is the floor. Voronoi
   polygons for ELM and multi-domain CPL stay out-of-scope.
5. **Renderer contracts uniform.** `render_section` follows
   the same envelope-out, oracle-recording pattern as the
   other three.
6. **Backwards compatibility.** All cycle-11 MPAS callers
   keep working unchanged. The `convention="auto"` default
   is the cycle-11 behavior.

## 5. Open risks

- **ELM `latixy`/`longxy` variable presence.** ELM restart
  files may not always ship the gridcell lat/lon directly
  (the `column` dim varies; `gridcell` is parent). If
  `latixy`/`longxy` missing from the test data, the renderer
  needs a clean error envelope, not a render attempt.
- **CPL domain selection ambiguity.** A file has multiple
  domain prefixes (`doma_`, `doml_`, `domo_`, `domi_`). The
  cycle-13 MVP defaults to `doma_` (atmosphere); other
  domains require an explicit `domain="doml"` kwarg. Document
  this clearly in the skill.
- **Great-circle sampling near the poles.** Numerical
  precision of haversine near (±90, *) is well-known to lose
  bits. Mitigation: use the standard `atan2` form, not the
  asin form; flag if `|lat| > 89.9`.
- **Cross-section endpoint cells coincide.** If `lat1==lat2`
  and `lon1==lon2` (degenerate), return a structured error
  rather than a zero-length array.
- **Bundle dispatch detection for ELM vs CPL.** Both new
  render kinds need the bundle smoke test updated; the
  existing CICE/EAMxx detection helpers shouldn't false-fire.
- **Test fixture sizes.** EAMxx mesh has 48k cells; ELM has
  15k gridcells. Synthesizing meshes at that scale slows
  unit tests. Use 50-cell synthetic meshes for unit tests;
  use the real bundled data only in integration tests.

## 6. Out-of-scope follow-ons (cycle 14+ candidates)

- ELM PFT / column-level rendering
- CPL multi-domain overlay
- Cross-section linear / area-weighted interpolation
- Cross-section time-animation
- `render_section` style-by-reference
- Multi-variable `read_slice` in one call
- `ncks --mro` per-record stride aggregation
- NCO operator parity: ncra, ncbo, ncea
- EAMxx dycore spectral-element grid
- Region clipping on map renderer (long carry)

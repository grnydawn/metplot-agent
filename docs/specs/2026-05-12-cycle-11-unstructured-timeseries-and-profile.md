# Cycle 11 — Unstructured time-series + vertical profile rendering

> Spec for cycle 11, building on the cycle-10 multi-file
> unstructured envelope (task E) to ship actual rendered output
> for time-series and vertical-profile plots on MPAS-family data.
> Driven by the v2 tester-guide pass
> (`docs/research/2026-05-12-tester-guide-pass-v2.md`) "Recommended
> next steps" section, which named time-series and profile as the
> highest-value reachable wins now that the paired-glob envelope
> is unblocked.

## 0. Why this spec is shaped this way

Cycle 10 task E unblocked the multi-file unstructured inspect
path: globbing 12 monthly Omega histories + a paired mesh now
returns `kind=local_multi`, `n_files=13`, `time.n=12`,
`spatial.coord_kind=unstructured`. The skill side ships a
"Multi-file unstructured time-series" subsection in
`netcdf-plot-timeseries/SKILL.md`, but the underlying tools
don't yet have the helpers the skill needs to actually pick a
cell, area-weight, and feed the existing `render_timeseries` /
`render_profile`.

Specifically:

- `read_slice` accepts `lat`/`lon` selectors for rectilinear /
  curvilinear (1-D or 2-D coord arrays) but not for unstructured
  (`(NCells,)` flat). The skill has no way to ask for "the cell
  nearest (40N, -65W)" or "all cells in the North Atlantic bbox".
- `compute_stats` has no cell-aware area-weighted reduction
  helper; for unstructured, the weights come from the mesh's
  `areaCell` (1-D array indexed by cell), not from
  `cos(deg2rad(lat))`.
- `render_timeseries` and `render_profile` already accept
  normalized 1-D series, so once the skill can compute the
  reduction, rendering is unchanged.

The fix is plumbed in the reader layer (new selector helpers +
extended `read_slice` semantics), with thin SKILL.md additions
and end-to-end verification on real Omega data. No new render
code paths.

## 1. Scope and success criteria

### Phase shape: single-phase

No library survey. All work in existing modules + small new
helper module(s). TDD red→green→commit per cycle 5/6/7/8/9/10
cadence.

### Success criteria

Cycle 11 is successful when all of the following hold against
real `data/omega/` files:

1. **Nearest-cell selector** — new
   `netcdf-reader.find_nearest_cell(mesh_path, lat, lon)` returns
   the integer cell index whose `(latCell, lonCell)` is closest
   to the requested `(lat, lon)` (great-circle distance, not
   Cartesian). Verified on `ocean_test_mesh.nc` with a known
   (lat, lon).
2. **Cells-in-bbox selector** — new
   `netcdf-reader.cells_in_bbox(mesh_path, lat_min, lat_max,
   lon_min, lon_max)` returns the integer cell indices whose
   `(latCell, lonCell)` falls inside the bbox. Handles
   cross-dateline bboxes (lon_min > lon_max) the same way the
   cycle-3 rectilinear region path does.
3. **read_slice cell-index selector** —
   `read_slice(..., cell_index=<int>)` and
   `read_slice(..., cell_indices=[...])` reduce the slice to one
   or more cells along the unstructured cell dim. Works with
   `mesh_path=` (so the slice carries the mesh reference for the
   renderer's audit trail).
4. **Multi-file glob single-cell time series** — paired-glob
   inspect of the 12 monthly Omega histories + cell-index
   selector + `time=all` yields a 12-element values array. End-
   to-end: `read_slice("ocn.hist.*.nc", "Temperature",
   cell_index=<id>, level=0, mesh_path=...)` returns
   `shape=[12]`.
5. **Multi-file global mean time series** — area-weighted mean
   via `areaCell` (or uniform mean fallback when `areaCell` not
   on the mesh) over all cells, all 12 timesteps → 12-element
   global-mean series.
6. **Multi-file regional mean time series** — cells_in_bbox +
   area-weighted mean → 12-element series for a North-Atlantic-
   sized bbox.
7. **Timeseries PNG rendered** — feeding the 12-element series to
   `render_timeseries` produces a non-trivial PNG with proper
   x-axis dates (Feb 0001 → Jan 0002), variable label, units. At
   least one PNG demonstrating each of the three reduction modes
   (single cell / global / regional).
8. **Vertical profile** —
   `read_slice("ocn.hist.0001-02-01...", "Temperature",
   time="first", cell_index=<id>, mesh_path=...)` returns
   `shape=[60]` (`NVertLayers`). Feeding to `render_profile`
   produces a profile PNG with depth (or layer index) on the
   inverted y-axis, temperature on x.
9. **Skill guidance shipped** —
   `netcdf-plot-timeseries/SKILL.md` "Multi-file unstructured
   time-series" subsection expanded with the actual procedure
   (find_nearest_cell / cells_in_bbox / cell_index selectors,
   areaCell weighting); a parallel
   `netcdf-plot-profile/SKILL.md` subsection added.
10. **Gates green** — `pytest -ra`, `ruff check`,
    `mypy src tools tests` all green on the merge commit; no
    new mypy errors beyond the pre-existing yaml-stub baseline.

## 2. Out of scope this cycle

- **CICE / EAMxx time-series and profile**. Same shape pattern
  but each family needs its own nearest-cell math (CICE 2-D
  `(nj, ni)` reshape; EAMxx 1-D `ncol`). Cycle 12+.
- **Multi-cell overlay time series** (multiple cells as multiple
  traces on one plot). Renderer already supports multi-series;
  the skill orchestration is what's missing — defer to cycle 12.
- **Named region lookup on unstructured**. The cycle-3
  `regions.json` returns bboxes that cycle-11
  `cells_in_bbox` can consume, but mapping a name like "North
  Atlantic" → bbox is a skill-side concern that already exists
  for rectilinear; the unstructured side just needs to pass the
  bbox through.
- **Seasonal / monthly aggregation on multi-file globs**. The
  cycle-3 `aggregation="monthly"` / `"seasonal"` parameter
  already works for the rectilinear path; verifying it on the
  unstructured multi-file path is a nice-to-have but not
  required for the cycle-11 success bar.
- **ELM / CPL plotting**. Detection-only stays the cycle-10
  shipping bar.
- **Region clipping for the map renderer** (long-deferred cycle
  9/10 §6).
- **EAMxx dycore** (carry-over).
- **Cross-section plots** (lon vs depth, lat vs depth) on
  unstructured — non-trivial because cells don't align on
  meridians/zonals; cycle 12+.

## 3. Affected surface

### 3.1 New selector helpers — `netcdf_reader/selectors_unstructured.py` (NEW)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/selectors_unstructured.py` (NEW) | `find_nearest_cell(mesh_ds, lat, lon)` — great-circle distance via haversine; returns `int`. `cells_in_bbox(mesh_ds, lat_min, lat_max, lon_min, lon_max)` — returns `np.ndarray[int]` of indices; handles cross-dateline (lon_min > lon_max) by splitting into two passes. Both reuse the cycle-9 `_to_degrees_if_radians` helper from `conventions/mpas.py` so radian meshes Just Work. |
| `src/mcp/netcdf_reader/selectors_unstructured.py` | `area_weights(mesh_ds, indices=None)` — returns a 1-D weights array (uses `areaCell` if present; else uniform-1 fallback). |

### 3.2 read_slice cell-index plumbing

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/tools/read_slice.py` | New keyword args `cell_index: int | None` and `cell_indices: list[int] | None`. When supplied, treat as an `isel` along whichever dim the variable uses for the cell axis (`NCells`/`nCells` case-insensitive). Mutually exclusive with `lat`/`lon` selectors — if both supplied, return `invalid_spec`. |
| `src/mcp/netcdf_reader/tools/resolve_spec.py` | Extend selector parsing to surface `cell_index` / `cell_indices` in `result.resolved`. |

### 3.3 Convenience MCP tool aliases (optional but spec-listed)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/server.py` | Expose the two new helpers as MCP tools (`find_nearest_cell`, `cells_in_bbox`) so skills can call them via the standard MCP boundary. Same shape as the existing `find_variables` / `find_time` helpers. |

### 3.4 Skills

| File | Change |
|---|---|
| `src/skills/netcdf-plot-timeseries/SKILL.md` | Replace the cycle-10 "Multi-file unstructured time-series" subsection (which was stub-only) with the full procedure: inspect glob + mesh → `find_nearest_cell` or `cells_in_bbox` → `read_slice` with `cell_index` / `cell_indices` + `time=all` → area-weighted mean (skill-side, using `area_weights`) → `render_timeseries`. Worked example with Omega Temperature. |
| `src/skills/netcdf-plot-profile/SKILL.md` | New subsection "Unstructured vertical profiles" mirroring the timeseries pattern: inspect (single file or glob) + mesh → `find_nearest_cell` → `read_slice` with `cell_index` + single time + all-levels → `render_profile`. |

### 3.5 Tests

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_selectors_unstructured.py` | NEW. Pin `find_nearest_cell` (synthetic mesh; deterministic nearest) + `cells_in_bbox` (rectangular + cross-dateline) + `area_weights` (with and without `areaCell`). |
| `tests/mcp/netcdf_reader/unit/test_read_slice_cell_index.py` | NEW. `read_slice(..., cell_index=N)` and `cell_indices=[...]` on synthetic Omega-shaped fixture. Mutually-exclusive check with `lat`/`lon`. |
| `tests/mcp/netcdf_reader/integration/test_real_omega_timeseries.py` | NEW. Skipped unless `data/omega/` present. Three end-to-end checks: single-cell timeseries (shape=[12]), global mean (shape=[12]), regional mean (shape=[12]). |
| `tests/mcp/netcdf_reader/integration/test_real_omega_profile.py` | NEW. Skipped unless `data/omega/` present. End-to-end: cell-index profile → shape=[60] (NVertLayers). |
| `tests/mcp/plot_renderer/unit/test_render_timeseries_unstructured.py` | NEW (or extend existing). Feed a synthetic 12-element series + axis to `render_timeseries`, verify PNG produced, oracle records the series labels. |
| `tests/mcp/plot_renderer/unit/test_render_profile_unstructured.py` | NEW (or extend). Synthetic 60-element series → profile PNG. |

### 3.6 Documentation

| File | Change |
|---|---|
| `README.md` | Capability table: add "Unstructured time-series + vertical profile (MPAS family, paired mesh) — shipping (cycle 11)". |
| `docs/architecture.md` | Brief subsection on the cell-index + area-weighting helpers; how they sit alongside the cycle-3 lat/lon selectors. |
| `docs/user-guide.md` | "Time-series on Omega data" walkthrough; "Profile on Omega data" walkthrough. |
| `docs/tester-guide.md` | New cases under §10 (timeseries) and §11 (profile) targeting `data/omega/`. |

## 4. Cross-cutting principles

1. **Reuse cycle-10 multi-file path verbatim.** No changes to
   `paths/multi_file.py`. The unstructured time-series workflow
   piggybacks on the already-shipping paired-glob inspect.

2. **TDD per cycle 5/6/7/8/9/10 cadence.** One task = one commit
   with tests. Red → green → commit.

3. **Selector helpers are pure / stateless.** Take a `mesh_ds` or
   `mesh_path` and the user inputs; return indices or weights.
   No caching, no mutating shared state.

4. **`render_timeseries` / `render_profile` contracts unchanged.**
   The renderers consume normalized 1-D series. Cycle 11 only
   adds upstream helpers; the render code stays as-is.

5. **Skill-side spatial reduction.** The skill computes the
   area-weighted mean (using `area_weights` from the helper),
   not the renderer. This keeps the rendering contract uniform
   across rectilinear and unstructured paths.

6. **No new third-party deps.** Haversine math is a 5-line numpy
   function; no scipy / sklearn needed.

7. **Backwards compatibility for read_slice.** The new
   `cell_index` / `cell_indices` kwargs are optional and ignored
   when the variable's dims don't include a cell axis. Existing
   `lat` / `lon` callers see no behavior change.

## 5. Open risks

- **Cross-dateline bbox semantics.** The cycle-3 rectilinear path
  has region-bounding logic for this; cycle 11 needs to mirror
  it on the unstructured side. Mitigation: borrow the
  cycle-3 region-clip semantics directly; split a
  `lon_min > lon_max` bbox into `[lon_min, 360]` plus `[0,
  lon_max]` (or analogous for `-180..180`).

- **`areaCell` not always shipped.** Omega `ocean_test_mesh.nc`
  ships `areaCell` (I should verify), but MPAS-Atmosphere or
  E3SM meshes may not. Mitigation: detect at `area_weights`
  call; fall back to uniform weighting with a structured
  warning so the agent surfaces "areaCell missing; using
  uniform weights — may bias high-latitude regions".

- **Mesh-file vs history-file dim casing.** The cycle-9 lesson:
  history files use uppercase `NCells`, mesh files use
  lowercase `nCells`. The cell-index `isel` in `read_slice`
  has to be case-insensitive on the cell dim name (same fix
  pattern as cycle-8 `validate_mesh_pair`).

- **Time axis from a multi-file concat may not be uniform.**
  Omega monthly histories should yield ~30-day cadence; the
  cycle-3 timeseries renderer expects monotonic time. Verify
  that `xr.open_mfdataset` concat preserves monotonicity.

- **Memory budget on single-cell × all-times.** 12 timesteps
  × 60 levels × 1 cell = 720 values — trivial. But a regional
  mean over ~500 cells × 60 levels × 12 timesteps could be a
  few MB; should fit `max_inline_bytes`. Document the threshold
  in the skill.

- **uxarray vs vanilla xarray for the helpers.** `find_nearest_cell`
  doesn't need uxarray (just numpy haversine). Keep it
  vanilla-xarray so the helper is callable from contexts that
  don't have uxarray installed (cycle-5 setup helper allows
  opting out of uxarray).

## 6. Out-of-scope follow-ons (cycle 12+ candidates)

- **CICE timeseries / profile** (extend cell-index plumbing to
  CICE's `(nj, ni)` shape).
- **EAMxx physics timeseries / profile** (extend to 1-D `ncol`).
- **Multi-cell overlay timeseries** (multi-series rendering of
  several cells on one plot).
- **Cross-section plots on unstructured** (cells along a chosen
  great-circle or meridian).
- **Named region lookup on unstructured** (skill-side glue
  between `regions.json` and `cells_in_bbox`).
- **Seasonal / monthly aggregation** verified on unstructured
  multi-file paths.
- **ELM / CPL plotting paths** (still carrying over from cycle
  10 §6).
- **EAMxx dycore** (still carrying over from cycle 9 §6).
- **Region clipping on the map renderer** (cycle 9/10 §6).

## End of spec

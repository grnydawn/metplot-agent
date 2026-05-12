# Cycle 8 — Unstructured-mesh plotting

> Spec for the unstructured-mesh plotting code path: net new
> `result.spatial.coord_kind = "unstructured"` shape on the inspect
> envelope, multi-file mesh-history pairing in `netcdf-reader`, a
> rendering branch in `plot-renderer` that knows about Voronoi cells,
> and skill-side guidance so the agent picks the right path. Driven by
> the cycle-6 Phase A failure_mode finding *"Unstructured-mesh
> coverage gap — 3/3 real-world files unplottable"*
> (`docs/research/2026-05-08-cycle-6-dogfood-findings.md`).
>
> Named in cycle-6 spec §7.1 as the follow-on cycle. Cycle 6 task 3
> already shipped three stepping stones in the same direction (MPAS
> convention detection, graceful time-decode failure, placeholder
> normalization); cycle 8 builds on top of those.

## 0. Why this spec is shaped this way

The cycle-6 dogfood tester had four real Earth-system files on disk
(MPAS-Ocean history + mesh, CICE restart, EAMxx restart). All four
are unstructured in one shape or another (Voronoi mesh, flattened
1-D blocked, spectral-element 4-D). The cycle-3 plot pipeline only
handles `coord_kind in {rectilinear, curvilinear}`, so 3 of the 3
real files (the synthetic test file passed because it was
constructed with a regular 73×144 grid) failed at the inspect →
plot gate. The "install-and-tool-surface" half of cycle 6 is now
clean, but the actual plotting half remains unusable for every file
the test user has on hand.

That gap is too big to refiner-fix and too cross-cutting for cycle
6 Phase B to absorb (it would have meant a new plotting code path,
a new convention detector module, multi-file load semantics, and
new SKILL.md pitfalls — well beyond the closed-loop applier work).
Cycle 6 §7.1 named it as cycle 8 and listed candidate tooling
(xarray-MPAS, uxarray, PyVista, datashader). Library selection was
explicitly deferred to "cycle 8 research phase."

This cycle therefore has two phases. Phase A picks the library +
validates it on the on-disk dogfood files. Phase B builds the MVP
plot path on top of that choice. The phases ship in order; the
spec at the end of Phase A may differ from the spec at the start
of Phase A — if Phase A's library survey reveals a constraint that
contradicts these requirements, this file gets rewritten before
Phase B begins, as a normal commit so the diff is visible in
`git log`.

## 1. Phases and success criteria

### Phase A — Library survey + validation on cycle-6 dogfood files

Survey the candidate tooling against the four real files cycle 6
left us with. Pick a primary library that can render at least the
MPAS-Ocean shape end-to-end. Document the choice with rationale +
the alternatives ruled out + the per-family coverage map.

**On-disk test files** (already present from cycle 6 dogfood):

- `ocean_mesh.nc` (MPAS-Ocean mesh; 7153 cells, 22403 edges, 11550
  vertices, 60 vertical levels; `latCell`/`lonCell`/`xCell` +
  Voronoi connectivity in `verticesOnCell`, `cellsOnVertex`)
- `ocn.hist.0001-02-01_00.00.00.nc` (MPAS-Ocean history; same
  dimensions paired with the mesh above; `Temperature`,
  `Salinity`, `SshCell`, `LayerThickness`)
- `cice.nc` (CICE5/6 restart; `ni=235160, nj=1` flattened
  block-decomposed; 31 untyped variables)
- `eamxx.nc` (E3SM EAMxx / SCREAM restart; dual-grid:
  physics `ncol=39620` + dycore spectral-element
  `elem=9905 × gp=4 × gp=4`)

**Phase A deliverables:**

- `docs/research/2026-05-NN-cycle-8-library-survey.md` —
  per-candidate evaluation with at least these dimensions:
  - Native unstructured-mesh primitives (Voronoi, triangular,
    spectral-element)?
  - xarray-native or own DataFrame model?
  - Multi-file mesh-history pairing supported out of the box?
  - Render-output format (matplotlib Figure, PIL, PyVista mesh,
    raw bytes)? metplot's `plot-renderer` returns a PNG path —
    library must terminate in a saveable raster.
  - Install footprint vs. the existing cartopy/scipy stack
    (cycle 5 dependency installer adds dep budget pressure).
  - Cartopy compatibility (we need projections for global maps).
  - License + maintenance signal as of May 2026.
- `.scratch/cycle-8-poc/` — one runnable PoC script per
  realistically-viable candidate, each producing a PNG of
  `Temperature[t=0, surface]` from the MPAS-Ocean history+mesh
  pair. The PoC scripts stay in `.scratch/` (gitignored); the
  research doc cites their existence + screenshots.
- Recommendation paragraph in the research doc naming the primary
  library + the secondary fallback (in case the primary blows up
  on EAMxx physics).

**Stop trigger:** user-driven. Phase A ends when the user signals
"library picked" — typically after the PoCs are visually
reviewable.

**Success-criteria evaluation** happens after the user signals
"library picked." The research doc is checked against:

1. **Does the chosen library produce a recognizable MPAS-Ocean
   surface-temperature map?** Visual smoke check on the PoC PNG.
2. **Is the per-family coverage map populated?** MUST: MPAS-Ocean
   (covers MPAS-A, MPAS-Seaice, Omega by inheritance). SHOULD:
   EAMxx physics `ncol`. MAY: CICE flattened block-decomposed.
   OUT: EAMxx dycore spectral-element (push to cycle 9+).

If Phase A picks a library but the library can't do EAMxx physics,
the cycle-8 scope contracts to MPAS-only and a §7 amendment notes
EAMxx as cycle 9.

### Phase B — Build the MVP unstructured plot path

Ship every change Phase A validated, in the same Claude-Code-first
posture cycle 6 took. Other hosts pick up the changes via the
shared `src/skills/...` build pipeline already in place from cycle
7; no per-host wiring needed beyond what cycles 4 and 7 wired.

**Phase B is successful when** all of the following hold:

- `netcdf-reader.inspect` on `ocean_mesh.nc` returns
  `result.spatial.coord_kind = "unstructured"`, with new fields
  `cell_dim`, `n_cells`, `lat_var`, `lon_var`, and (for polygon
  fill) `vertex_lat_var`, `vertex_lon_var`,
  `vertices_on_cell_var`.
- `netcdf-reader.inspect` on `ocn.hist.0001-02-01_00.00.00.nc`
  (history-only, no spatial coords in-file) detects the missing
  geometry and surfaces it via a new `ambiguous`-class envelope
  subcode `mesh_pairing_required` with the suggested pair path
  derived from the basename convention (`*_mesh.nc` /
  `init.nc` / `ocean.mesh.*.nc`).
- A new `netcdf-reader.inspect(path, mesh_path=...)` two-file
  call resolves the pair, returns a single combined inspect
  envelope where `spatial` is populated from the mesh and
  `variables` is populated from the history (variables that share
  the cell dim with the mesh are tagged `grid_kind:
  "cell_centered"`).
- `plot-renderer.render_map` accepts an `unstructured` envelope
  (or a {history, mesh} pair) and produces a recognizable map
  for `Temperature[t=0, surface]` on the MPAS-Ocean fixture pair.
- `netcdf-plot-map/SKILL.md` has a new "Unstructured-mesh files"
  Pitfalls subsection + a procedure for the mesh-pairing prompt.
- `pytest -ra`, `ruff check`, and `mypy src tools tests` are
  green on the merge commit.

### Out of scope this cycle

- **CICE block grid** unless Phase A's secondary fallback handles
  it cleanly. The 235160×1 layout is genuinely pathological and
  needs the matching CICE grid file (which we don't have in the
  dogfood set). Likely cycle 9.
- **EAMxx dycore spectral-element** rendering. The `elem×gp×gp`
  shape needs HOMME-aware reconstruction; far enough off the
  plot-from-NetCDF main path to defer.
- **Contour / streamline on unstructured grids**. MVP is filled
  scatter or polygon — line geometries on Voronoi meshes are a
  separate problem.
- **GPU rendering paths.** Datashader is fine for raster
  rendering at scale; vispy / pyvista interactive 3-D is not in
  scope.
- **Regridding to a synthetic regular grid** for legacy tooling
  compatibility. Native rendering on the unstructured grid is
  the cycle-8 deliverable; regridding is a separate cycle.
- **The `add_region` applier op** (still zero region findings).
- **Cycle-9 spec drafting.** Cycle 9's scope depends on what
  Phase A's library coverage map shows; the spec waits.

## 2. Phase A artifacts

### 2.1 Library survey doc — `docs/research/2026-05-11-cycle-8-library-survey.md`

Created at start of Phase A. Sections:

1. **Candidate list** — `uxarray`, `PyVista`, `datashader`,
   `holoviews/hvplot` (built on datashader), raw matplotlib
   `tripcolor` + custom Voronoi unflattening (via
   `mpas_tools.viz.mesh_to_triangles`). Add or remove candidates
   as research surfaces them. (Phase A research, 2026-05-11:
   dropped `xarray-mpas` from the original candidate list —
   verified it does not exist as a standalone package on PyPI or
   GitHub; the spec's prior reference was a confusion with the
   deprecated `pwolfram/mpas_xarray` repo, which was superseded by
   MPAS-Analysis. See library-survey doc §6.)
2. **Per-candidate evaluation matrix** (one column per dimension
   listed in Phase A deliverables above; one row per candidate).
3. **PoC results** — link each candidate to its
   `.scratch/cycle-8-poc/<name>.py` script + the produced PNG.
   Note install pain, runtime, output quality.
4. **Recommendation** — primary library + secondary fallback +
   the dimensions where the primary is weak.
5. **Coverage map** — table of {MPAS-Ocean, MPAS-A, MPAS-Seaice,
   Omega, EAMxx physics, EAMxx dycore, CICE flattened} ×
   {primary, fallback} → {supported, partial, out-of-scope}.

### 2.2 PoC scripts — `.scratch/cycle-8-poc/`

Gitignored. One Python script per candidate. Each takes
`/home/youngsung/repos/github/metplot-agent/ocean_mesh.nc` and
`/home/youngsung/repos/github/metplot-agent/ocn.hist.0001-02-01_00.00.00.nc`
as inputs (or stages copies in `.scratch/`) and produces
`out-<candidate>.png` of `Temperature[t=0, surface]`. No tests in
`.scratch/`; this is research workspace.

## 3. Phase B affected surface

### 3.1 New convention-detection coverage

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/mpas.py` | Already exists from cycle 6. May need light additions for cell-centered-variable detection — flag variables whose first non-time dim is the cell dim. |
| `src/mcp/netcdf_reader/conventions/cice.py` (NEW) | Detect CICE5/6 via the variable-name fingerprint (`aicen`, `vicen`, `Tsfcn`, `iceumask`, …). MAY ship; depends on Phase A coverage. |
| `src/mcp/netcdf_reader/conventions/eamxx.py` (NEW) | Detect E3SM-EAMxx via `case` + `source` attrs + the `ncol` dim. MAY ship; depends on Phase A coverage. |

### 3.2 Inspect envelope — unstructured spatial shape

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/cf.py` | New `extract_unstructured_spatial(ds, convention)` helper that returns the new spatial shape: `{coord_kind: "unstructured", cell_dim, n_cells, lat_var, lon_var, vertex_lat_var?, vertex_lon_var?, vertices_on_cell_var?, lon_convention, lat_range, lon_range}`. |
| `src/mcp/netcdf_reader/tools/inspect.py` | Branch on `convention.primary == "MPAS"` (and any new conventions Phase A adds) to call the unstructured spatial extractor instead of `extract_spatial`. |
| `src/mcp/netcdf_reader/envelope.py` | New `AmbiguitySubcode.MESH_PAIRING_REQUIRED` for the history-without-mesh case. New `WarningCode.UNSTRUCTURED_GRID` to flag MAY-cycle-9 cases (CICE, EAMxx dycore) where we detect but don't render. |

### 3.3 Multi-file mesh-history pairing

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/mesh_pair.py` (NEW) | Pairing heuristics: history basename → likely mesh basenames in the same directory (`<base>_mesh.nc`, `*.mesh.*.nc`, `init.nc`); dim-match validation (same `nCells` / `nEdges` etc.). |
| `src/mcp/netcdf_reader/tools/inspect.py` | New optional `mesh_path` parameter. If absent and the file is unstructured-but-coordless, emit the `mesh_pairing_required` ambiguous envelope. If present, open both files and merge geometry-from-mesh + variables-from-history. |
| `src/mcp/netcdf_reader/tools/read_slice.py` | Same — accept `mesh_path` so slicing can attach `latCell` / `lonCell` to the slice output. |
| `src/mcp/netcdf_reader/tools/resolve_spec.py` | Honor `mesh_path` end-to-end. |

### 3.4 Renderer — unstructured map path

| File | Change |
|---|---|
| `src/mcp/plot_renderer/tools/render_map.py` | New `_render_unstructured_map(...)` branch keyed on `spatial.coord_kind == "unstructured"`. Implementation per Phase A's library pick. |
| `src/mcp/plot_renderer/tools/__init__.py` | Register the new render branch in the tools dict. |

### 3.5 Skills

| File | Change |
|---|---|
| `src/skills/netcdf-inspect/SKILL.md` | Pitfalls subsection on mesh-history pairing (when inspect returns `mesh_pairing_required`, prompt user for `mesh_path`). |
| `src/skills/netcdf-plot-map/SKILL.md` | "Unstructured-mesh files" Pitfalls subsection + procedure: detect `coord_kind == "unstructured"`, route to render_map's unstructured branch, expect a polygon-fill or cell-centered scatter rather than `imshow`. |
| `src/skills/netcdf-inspect/references/aliases.md` | (Already covered by cycle-6 task-3 follow-on — the TEOS-10 alias finding is queued as a refinement draft, not in this spec's scope.) |

### 3.6 Test surface

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_unstructured_spatial.py` | NEW. extract_unstructured_spatial on synthetic MPAS-shaped Dataset. |
| `tests/mcp/netcdf_reader/unit/test_mesh_pair.py` | NEW. Pairing heuristics + dim-match validation. |
| `tests/mcp/netcdf_reader/unit/test_inspect_unstructured.py` | NEW. inspect on synthetic MPAS-Ocean mesh+history pair. |
| `tests/mcp/plot_renderer/unit/test_render_map_unstructured.py` | NEW. Render path on synthetic unstructured envelope; PNG produced, non-trivial pixel variance. |
| `tests/mcp/netcdf_reader/integration/test_real_files.py` | EXTEND. Real-file integration on `ocean_mesh.nc` + `ocn.hist.*.nc` (currently skipped — flip on if real files present at standard path). |
| `tests/skills/integration/test_unstructured_map_flow.py` | NEW. End-to-end skill-flow test: inspect → mesh_path prompt → read_slice → render_map → PNG produced. |

### 3.7 Documentation

| File | Change |
|---|---|
| `README.md` | Status line update: "unstructured-mesh plotting is shipping for the MPAS family." |
| `docs/architecture.md` | New subsection under "Self-improvement layer" or alongside it covering the unstructured-mesh path. Update the `result.spatial.coord_kind` enumeration. |
| `docs/dogfood-tester-guide.md` | Optional — note that unstructured-mesh files now work for the MPAS family. |
| `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md` §7.1 | Add a "Shipped" status note pointing at the cycle 8 merge commit. |

## 4. Cross-cutting principles

1. **TDD per cycle 5 / 6 / 7 cadence.** One task = one commit + tests. Red → green → commit. PoC scripts in `.scratch/` are exempt; they're research artifacts.

2. **Library choice is reversible.** The unstructured render branch sits behind one function (`_render_unstructured_map`). Swapping libraries mid-Phase-B should be a single-file change plus PoC re-run, not a multi-file refactor. Avoid letting the chosen library's idioms leak into surrounding code.

3. **The inspect envelope is the contract.** Renderer + skills consume `result.spatial.coord_kind` and the supporting fields. Library specifics never leak past the netcdf-reader boundary.

4. **Mesh-pairing is opt-in, never silent.** When inspect returns `mesh_pairing_required`, the user (or agent) supplies `mesh_path` explicitly. The applier never guesses — file-path heuristics are *suggestions*, not auto-applies.

5. **No regressions on the rectilinear/curvilinear path.** The existing cycle-3 plot pipeline still owns 100% of regular-grid files. Cycle 8 only adds a new branch.

6. **Graceful degradation on unsupported sub-families.** If we detect EAMxx dycore or CICE-flattened-without-grid, return a structured `unstructured_grid` warning naming the family + the deferral cycle, not a crash and not a silent fallback.

7. **Render output stays PNG.** Cycle 2's `render_map` returns a PNG path. Cycle 8 doesn't change that contract — even if the chosen library has fancier output options (interactive HTML, PyVista 3-D scenes), the cycle-8 deliverable is a saveable raster.

8. **Dependency footprint stays inside cycle-5's installer budget.** If Phase A's primary library needs a non-trivial install (e.g. PyVista pulls VTK), cycle 5's `setup.sh` gets an optional `--no-unstructured` flag and a documented opt-out.

## 5. Open risks

- **Library churn.** uxarray and similar climate-mesh libraries are young projects (≤3 years old as of May 2026). API stability is a real concern; pin versions tightly and document the pin. (`xarray-mpas` — originally listed as a candidate — turned out not to exist as a standalone package; see survey doc §6.)

- **VTK/PyVista install footprint.** PyVista pulls VTK (~50 MB). If selected as primary, cycle 5's installer needs a graceful path for users who can't or don't want that dep.

- **MPAS-A vs MPAS-Ocean coord conventions.** MPAS-Atmosphere may differ subtly (degree vs. radian on `latCell`?). Phase A PoC catches it on `ocean_mesh.nc`; an MPAS-A fixture would catch the inverse. If a user reports an MPAS-A file failing, we adapt.

- **Performance on full-resolution meshes.** 7153 cells is the dogfood toy size; real MPAS-Ocean meshes are 1M+ cells. Render time and memory must be measured during Phase A. If the chosen library can't handle a 1M-cell mesh in <30s on the test machine, datashader-style raster aggregation needs to be in the fallback path.

- **Voronoi connectivity vs. simpler scatter.** Polygon fill (Voronoi cell shading) is the "correct" rendering; cell-centered scatter is a degraded fallback. Phase A picks the default; both paths should be reachable via a render parameter.

- **`mesh_path` ergonomics.** If the user has to type the mesh path every time, the loop friction is high. Phase B may need a small "mesh path remembered for this session" cache (or rely on the skill-refiner loop from cycle 6 to learn the mesh path per directory).

## 6. Out-of-scope follow-ons (cycle 9+ candidates)

- **EAMxx dycore spectral-element rendering.** Needs HOMME-aware reconstruction; significant new code.
- **CICE flattened block-decomposed grid.** Needs the matching CICE `grid.nc` file and a custom unflattening step.
- **Time-series and profile plots on unstructured grids.** Cycle 8 covers map only; the timeseries + profile skills need their own unstructured branch.
- **Region clipping on unstructured grids.** Cycle 3 region-bounds work assumes rectilinear; an unstructured-aware region-clip is a separate problem.
- **Multi-file globbing for unstructured time series.** The cycle-1 `multi_file_combine` assumes a regular time concat across rectilinear files. Multi-file unstructured timeseries is cycle 9+.
- **Interactive 3-D mesh viewers.** PyVista scenes, vispy, etc. Out of scope; render output stays raster PNG.
- **Performance optimization for 1M+ cell meshes** beyond what Phase A confirms is workable.
- **MPAS-Atmosphere / MPAS-Seaice fixtures + tests.** Cycle 8 ships the code path validated on MPAS-Ocean; cycle 9+ can add per-family test fixtures.

## End of spec

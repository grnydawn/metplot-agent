# Cycle 9 — CICE flattened grids + EAMxx physics grid

> Spec for the next unstructured-mesh coverage step: extend the
> `coord_kind = "unstructured"` envelope and the mesh-pairing
> infrastructure cycle 8 shipped to two additional sub-families that
> currently fall out of the inspect → plot pipeline: CICE5/6
> flattened block-decomposed restarts and E3SM-EAMxx physics-column
> output. Both sub-families were named "out of scope (cycle 9+)" in
> the cycle-8 spec §1.0 and §6, and both have on-disk dogfood files
> from the cycle-6 dogfood set that today produce `spatial: null`.

## 0. Why this spec is shaped this way

The cycle-6 dogfood pass left four real Earth-system files on the
machine. Cycle 8 unlocked one of them end-to-end (MPAS-Ocean
mesh+history pair). Two remain blocked:

- **`cice.nc`** (CICE5/6 restart, 66 MB). Inspect today returns
  `convention.primary = "unknown"` and `spatial: null`. The file
  has 31 variables on `(nj=1, ni=235160)` with the classic CICE
  fingerprint (`aicen`, `vicen`, `Tsfcn`, `iceumask`,
  `stressp_1..4`, `uvel`, `vvel`). Coordinates are not in the
  file; geometry lives in a separate CICE grid file shared by all
  restarts of the run.
- **`eamxx.nc`** (E3SM EAMxx / SCREAM restart, 2.2 GB). Inspect
  today returns `convention.primary = "CF"` (CF-1.8 declared) with
  rich `standard_name` metadata, but `spatial: null` because there
  is no `lat`/`lon` coordinate variable in the file — the file
  ships dual-grid output (physics `ncol=39620`, dycore
  `elem=9905 × gp=4 × gp=4`) and the geometry for both grids lives
  in separate scrip / mapping files.

The shape of both gaps is identical to MPAS: **history files
shipped without geometry**. The cycle-8 mesh-pair infrastructure
(`mesh_pairing_required` ambiguous envelope, `mesh_path=`
two-file inspect, paired-envelope merge) is directly reusable.
What cycle 9 has to add is:

1. **Two new convention detectors** (`cice`, `eamxx`) that pull
   these files out of `convention: unknown` / `convention: CF` and
   route them onto the unstructured branch.
2. **Two new geometry sources** in the spatial extractor: CICE
   2-D curvilinear `TLAT/TLON` (when reshaped from `(nj, ni)`) and
   EAMxx physics-grid 1-D `lat[ncol]/lon[ncol]`.
3. **Two new render paths** in `_render_unstructured_map`: scatter
   or `tripcolor` for the no-polygon-connectivity case (both CICE
   and EAMxx ship cell centers but no vertex/cell-on-vertex
   tables).

EAMxx **dycore** (`elem × gp × gp` spectral-element) stays out of
scope — that needs HOMME-aware GLL-point reconstruction and a
separate render branch. Cycle 9 covers EAMxx physics only.

## 1. Scope and success criteria

### Phase shape: single-phase

Library choice (uxarray + matplotlib for polygon fill;
matplotlib scatter / `tripcolor` for center-only meshes) carries
over from cycle 8 Phase A. The dependency budget already absorbed
uxarray + datashader in cycle 8; no new library survey.

If during implementation a new library need surfaces (e.g.,
`xesmf` for EAMxx remap on the fly), it gets logged as a deviation
in `docs/research/2026-05-NN-cycle-9-deviations.md` and the spec
amended before merging — same TDD-with-deviations cadence as
cycles 5–8.

### Success criteria

Cycle 9 is successful when all of the following hold against the
on-disk dogfood files (or, where grid files are unavailable, the
synthetic fixtures listed under §3.6):

1. **CICE convention detection**:
   `netcdf-reader.inspect(cice.nc)` returns
   `convention.primary = "CICE"`, evidence cites the variable-name
   fingerprint (`aicen`, `vicen`, `Tsfcn`, `iceumask`, …).
2. **EAMxx convention detection**:
   `netcdf-reader.inspect(eamxx.nc)` returns
   `convention.primary = "EAMxx"` (or `"E3SM-EAMxx"`), evidence
   cites `source` attr ("E3SM Atmosphere Model (EAMxx)") and the
   `ncol` + `elem` + `gp` dim shape.
3. **History-without-geometry ambiguity**: bare `inspect` on
   either file returns `ok: false` with subcode
   `mesh_pairing_required` and a `candidates` list of likely
   grid-file basenames in the same directory
   (`*_grid.nc`, `grid.nc`, `*_scrip.nc`,
   `*ne30pg2*.nc`, `*ne4pg2*.nc`, etc., per family).
4. **Paired inspect for CICE**:
   `inspect(cice.nc, mesh_path=<cice_grid.nc>)` returns a combined
   envelope with `spatial.coord_kind = "unstructured"`,
   `cell_dim = "ni"`, `n_cells = <nj * ni from grid>`, plus
   `lat_var = "TLAT"`, `lon_var = "TLON"` (and U-grid analogs if
   the file ships them). Variables whose `(nj, ni)` matches the
   grid's are tagged `grid_kind: "cell_centered"`.
5. **Paired inspect for EAMxx physics**:
   `inspect(eamxx.nc, mesh_path=<phys_grid.nc>)` returns a
   combined envelope with `spatial.coord_kind = "unstructured"`,
   `cell_dim = "ncol"`, `n_cells = 39620`, plus
   `lat_var = "lat"`, `lon_var = "lon"`. Variables on the `ncol`
   axis are tagged `grid_kind: "cell_centered"`; dycore-axis
   variables (`elem × gp × gp`) are tagged
   `grid_kind: "dycore_spectral"` and surfaced with a
   `unstructured_dycore_unsupported` warning instead of erroring.
6. **Render for CICE**: `plot-renderer.render_map` produces a
   recognizable map of a CICE field (`aicen`, `Tsfcn`, or `uvel`)
   on the paired envelope, using scatter or `tripcolor` (CICE grid
   files typically do not ship vertex connectivity).
7. **Render for EAMxx physics**: `plot-renderer.render_map`
   produces a recognizable map of a physics variable (`T_mid` or
   `ps`) on the paired envelope.
8. **Graceful EAMxx dycore handling**: requesting a plot of a
   dycore-axis variable (`v_dyn`, `vtheta_dp_dyn`, `dp3d_dyn`,
   `phi_int_dyn`, `Qdp_dyn`, `w_int_dyn`, `phis_dyn`, `ps_dyn`)
   returns an `ok: false` envelope with
   `error.code = "unstructured_dycore_unsupported"` and a pointer
   to cycle 10+ rather than a crash.
9. **Skills updated**: both `netcdf-inspect/SKILL.md` and
   `netcdf-plot-map/SKILL.md` have the CICE + EAMxx subsections
   added; the "Other unstructured conventions … NOT yet covered
   (cycle 9+)" disclaimer in `netcdf-inspect/SKILL.md` is removed
   for the now-covered cases and rewritten to call out the
   remaining EAMxx dycore gap.
10. **Gates green**: `pytest -ra`, `ruff check`, and
    `mypy src tools tests` are all green on the merge commit.

### What "recognizable map" means

For criteria 6 and 7, the visual smoke check is:
- Field values vary across the map (not a single-color blob).
- Land/ocean mask is visible on CICE (most ice fields are zero
  outside polar regions; the global plot should show a band of
  meaningful values at high latitudes and zero/NaN elsewhere).
- For EAMxx `T_mid` (surface level), there is a recognizable
  equator-pole gradient.
- Cartopy projection works (Robinson or PlateCarree); coastlines
  drawn.

## 2. Out of scope this cycle

The same reversibility principle from cycle 8: anything that
materially changes a non-cycle-9 code path is excluded.

- **EAMxx dycore spectral-element rendering** (`elem × gp × gp`).
  Needs HOMME-aware GLL-point reconstruction (per-element tensor
  remap to a regular sub-element grid, then global mosaic). This
  is a substantial separate piece of work. Cycle 9 detects it,
  surfaces a structured warning, and refuses to plot. Cycle 10+.
- **Auto-derived CICE grid reconstruction**. If the user has *only*
  the CICE restart (no grid file), cycle 9 returns
  `mesh_pairing_required` with candidates but does not attempt to
  infer geometry from block-decomposition metadata. (The restart
  alone does not contain `nblocks`, `nx_block`, `ny_block`, or
  `block_decomp`. The information is genuinely not in the file.)
- **Contour / streamline on unstructured grids**. MVP is filled
  scatter / tripcolor / polygon; line geometries on cell-centered
  point clouds are a separate problem.
- **Region clipping on unstructured grids**. Still cycle 10+ as
  flagged in cycle 8 §6.
- **Time-series and profile plots on unstructured grids**. Cycle 9
  covers map only; the timeseries + profile skills' unstructured
  branches are cycle 10+.
- **Multi-file globbing for unstructured time series**. Same as
  cycle 8 §6.
- **U-grid (CICE `ULAT`/`ULON`) staggered handling**. If the CICE
  grid file ships both T and U coordinates, cycle 9 picks T by
  default; choosing U for the few uvel/vvel cases is a follow-on.
- **The `add_region` applier op** (still zero region findings;
  applier op stays stubbed).

## 3. Affected surface

### 3.1 Convention detection

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/cice.py` (NEW) | Detect CICE5/6 via variable-name fingerprint. Required: ≥3 of `{aicen, vicen, vsnon, Tsfcn, iceumask, stressp_1, uvel, vvel}` present. Also reports the `(nj, ni)` shape so the spatial extractor can pair against the grid file. |
| `src/mcp/netcdf_reader/conventions/eamxx.py` (NEW) | Detect EAMxx via `source` attr matching `r"EAMxx|SCREAM"` OR `case` attr containing `SCREAM`. Reports the present grid axes (`ncol` for physics, `(elem, gp, gp)` for dycore). |
| `src/mcp/netcdf_reader/conventions/__init__.py` | Register the two new detectors in the dispatch list. Order: CF → WRF → ROMS → MPAS → EAMxx (CF-prior) → CICE (unknown-prior). |

### 3.2 Inspect envelope — unstructured spatial for new families

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/cice.py` | Add `extract_spatial_cice(history_ds, grid_ds)`. The grid file ships `TLAT(nj, ni)` and `TLON(nj, ni)` as degrees. Validate that `history.nj * history.ni == grid.nj * grid.ni`; reshape if the history was flattened. Returns the unstructured envelope with `cell_dim = "ni"`, `n_cells`, `lat_var = "TLAT"`, `lon_var = "TLON"`, and `vertex_*` only if the grid file ships `latt_bounds`/`lont_bounds`. |
| `src/mcp/netcdf_reader/conventions/eamxx.py` | Add `extract_spatial_eamxx(history_ds, grid_ds)`. The grid file ships `lat[ncol]`, `lon[ncol]` (1-D). Vertices come from `grid_corner_lat[ncol, 4]` / `grid_corner_lon[ncol, 4]` if present (SCRIP-style). Returns the unstructured envelope with `cell_dim = "ncol"`. |
| `src/mcp/netcdf_reader/conventions/mpas.py` | No change (cycle 8 already covers it). |
| `src/mcp/netcdf_reader/tools/inspect.py` | Extend the branch from cycle 8 (currently `convention.primary == "MPAS"`) to also dispatch to `extract_spatial_cice` / `extract_spatial_eamxx`. Same `mesh_path` parameter; same ambiguous-envelope behavior on bare history. |
| `src/mcp/netcdf_reader/envelope.py` | New `ErrorCode.UNSTRUCTURED_DYCORE_UNSUPPORTED` for the EAMxx dycore deferral. New `WarningCode.DYCORE_VARS_PRESENT` (emitted on EAMxx physics-grid plots so the agent surfaces "this file also contains dycore-axis vars; those aren't plottable yet"). |

### 3.3 Mesh-pair heuristics — extend for CICE and EAMxx

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/mesh_pair.py` | Extend the candidate-ranking heuristic to also surface:  - CICE: `*_grid.nc`, `grid.nc`, `*pop_grid*.nc`, `gx*v*.nc` in the same directory.  - EAMxx physics: `*scrip*.nc`, `ne*pg2*.nc`, `ne*pg2*lonlat*.nc`. The validator must accept the case where `history.nj * history.ni == grid.nj * grid.ni` (CICE flattening) and the case where `history.ncol == grid.ncol` (EAMxx physics). |
| `src/mcp/netcdf_reader/tools/read_slice.py` | `mesh_path` param plumbing for CICE + EAMxx (currently cycle 8 only handles MPAS via the unified unstructured branch). |
| `src/mcp/netcdf_reader/tools/resolve_spec.py` | Vertical-dim recognition for CICE (`nilyr`, `nslyr`, `nkice`, `nkbio`, `ncat`) and EAMxx (`lev`, `ilev` — already recognized but verify case-insensitive). |

### 3.4 Renderer — center-only unstructured branch

| File | Change |
|---|---|
| `src/mcp/plot_renderer/tools/render_map.py` | Add a sub-branch inside `_render_unstructured_map` for the center-only case (no `vertices_on_cell_var`): use `matplotlib.pyplot.scatter(lon, lat, c=values, s=<dot>)` with a Cartopy `transform=ccrs.PlateCarree()` projection, or `matplotlib.pyplot.tripcolor(triangulation, values)` if 1-D unstructured (EAMxx physics). For CICE (2-D `TLAT/TLON` array), use `pcolormesh` since the grid is curvilinear after reshape — closer to a curvilinear-2D case than to a Voronoi case. |
| `src/mcp/plot_renderer/tools/render_map.py` | Add the dycore-axis early-exit: if the requested variable's first non-time dim is `elem` (or shape matches `(elem, gp, gp)`), return `unstructured_dycore_unsupported` error envelope. |

### 3.5 Skills

| File | Change |
|---|---|
| `src/skills/netcdf-inspect/SKILL.md` | Extend the "Unstructured grids — MPAS family" Pitfalls subsection (added in cycle 8) into a section that also covers CICE and EAMxx mesh-pair flows. Remove the "Other unstructured conventions … NOT yet covered (cycle 9+)" disclaimer; replace with a narrower "EAMxx dycore … cycle 10+" note. |
| `src/skills/netcdf-plot-map/SKILL.md` | Add subsections "CICE history files" and "EAMxx physics-grid files" mirroring the existing MPAS subsection — when to expect each, what the paired-call shape looks like, what the render output will look like (scatter for EAMxx, pcolormesh for CICE-after-reshape). Note the dycore early-exit. |
| `src/skills/netcdf-inspect/references/aliases.md` | (No change required; CICE/EAMxx var names already self-describe via standard_name metadata where present.) |

### 3.6 Test surface — fixtures + tests

CICE and EAMxx grid files are **not** on disk in this repo. Tests
therefore use synthetic fixtures that match the on-disk shapes
exactly (constructed in test setup with the same dim names and
matching cell counts).

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_convention_cice.py` | NEW. Detect via variable-name fingerprint; reject files with too few CICE-fingerprint vars. |
| `tests/mcp/netcdf_reader/unit/test_convention_eamxx.py` | NEW. Detect via `source` / `case` attrs; reject files lacking both. |
| `tests/mcp/netcdf_reader/unit/test_spatial_cice.py` | NEW. `extract_spatial_cice` against synthetic CICE history (`nj=1, ni=24`) + synthetic CICE grid (`nj=4, ni=6, TLAT, TLON`). Verify reshape, `n_cells = 24`, `cell_dim = "ni"`. |
| `tests/mcp/netcdf_reader/unit/test_spatial_eamxx.py` | NEW. `extract_spatial_eamxx` against synthetic EAMxx physics-grid history (`ncol=100`) + synthetic scrip file (`ncol=100, lat, lon, grid_corner_lat[100, 4], grid_corner_lon[100, 4]`). |
| `tests/mcp/netcdf_reader/unit/test_inspect_paired_cice.py` | NEW. End-to-end inspect on synthetic CICE pair. |
| `tests/mcp/netcdf_reader/unit/test_inspect_paired_eamxx.py` | NEW. End-to-end inspect on synthetic EAMxx physics pair. Verify dycore-axis variables tagged `dycore_spectral` and unstructured warning emitted. |
| `tests/mcp/netcdf_reader/unit/test_mesh_pair_cice_eamxx.py` | NEW. Extend cycle-8's `test_mesh_pair.py` patterns to CICE and EAMxx basename heuristics. |
| `tests/mcp/plot_renderer/unit/test_render_map_cice.py` | NEW. Renderer on synthetic CICE-paired envelope; PNG produced, non-trivial pixel variance. |
| `tests/mcp/plot_renderer/unit/test_render_map_eamxx.py` | NEW. Renderer on synthetic EAMxx-physics envelope; PNG produced. |
| `tests/mcp/plot_renderer/unit/test_render_map_dycore_refusal.py` | NEW. Renderer returns `unstructured_dycore_unsupported` on dycore-axis variable. |
| `tests/skills/integration/test_unstructured_flow_cice.py` | NEW. End-to-end skill flow: inspect → mesh_pair prompt → paired inspect → read_slice → render_map → PNG. |
| `tests/skills/integration/test_unstructured_flow_eamxx.py` | NEW. Same for EAMxx physics. |
| `tests/mcp/netcdf_reader/unit/test_unstructured_spatial.py` | EXTEND. Cycle-8 MPAS coverage still passes. |
| `tests/mcp/netcdf_reader/unit/test_inspect_paired.py` | EXTEND. Cycle-8 MPAS coverage still passes. |

### 3.7 Documentation

| File | Change |
|---|---|
| `README.md` | Update the capability table: "CICE5/6 flattened block-decomposed grids → shipping (cycle 9)" and "EAMxx physics column grid → shipping (cycle 9)". Update the "Out of scope" line to remove CICE and EAMxx-physics; leave EAMxx-dycore in the out-of-scope list. |
| `docs/architecture.md` | Extend the unstructured-mesh path subsection with the CICE 2-D-reshape and EAMxx 1-D-physics cases. |
| `docs/user-guide.md` | Add a "CICE files" walkthrough and an "EAMxx files" walkthrough mirroring the existing MPAS walkthrough. |
| `docs/tester-guide.md` | Add §3.13–§3.16 (inspect cases for CICE/EAMxx), §8.4–§8.7 (plot cases), §9.4–§9.5 (mesh-pair cases for CICE/EAMxx), §20.X (dycore refusal). |
| `docs/specs/2026-05-11-cycle-8-unstructured-mesh-plotting.md` §6 | Append a "Shipped in cycle 9 (`<merge sha>`): CICE flattened + EAMxx physics" note. |

## 4. Cross-cutting principles

1. **Reuse cycle-8 infrastructure where possible.** `mesh_pairing_required`, `mesh_path=`, the paired envelope merge — these are already in place. Cycle 9 adds detectors and per-family extractors; it does not invent new envelope shapes for new families.

2. **TDD per cycle 5 / 6 / 7 / 8 cadence.** One task = one commit + tests. Red → green → commit.

3. **Library choice is reversible** (same as cycle 8 §4.2). The center-only render branch lives behind one function (`_render_unstructured_center_only`). Swapping renderer libraries (e.g., from matplotlib scatter to datashader for very large `ncol`) is a single-file change.

4. **The inspect envelope remains the contract** (same as cycle 8 §4.3). All cycle-9 changes manifest as fields populated on the existing unstructured envelope shape.

5. **Mesh-pairing is opt-in, never silent.** When inspect returns `mesh_pairing_required` for CICE or EAMxx, the user (or agent) supplies `mesh_path` explicitly. The applier never guesses.

6. **No regressions on rectilinear / curvilinear / MPAS paths.**

7. **Graceful degradation on EAMxx dycore.** Detect, surface a structured error / warning, point at cycle 10+. Do not crash. Do not fall back silently.

8. **Render output stays PNG.** Same as cycle 8 §4.7.

9. **Dependency footprint stays inside cycle-5's installer budget.** No new install-tier dependencies expected; if surveying surfaces a need (e.g., `xesmf`), it triggers a spec amendment.

## 5. Open risks

- **No CICE / EAMxx grid files on disk.** This is the biggest gap.
  Cycle 8 had `ocean_mesh.nc` next to `ocn.hist.*.nc`. Cycle 9 has
  *neither* a CICE grid file nor an EAMxx physics-grid scrip file.
  Mitigation: build the code path against synthetic fixtures of
  the same shape; the real-file dogfood pass is a follow-on once
  the user acquires the grid files. Treat this as an explicit
  P2-blocker on success criterion #6 + #7 (the "recognizable map"
  check) for the *real* dogfood files — synthetic-fixture
  rendering covers the contract, real-file rendering is the
  follow-on.

- **CICE flattening recovery is fragile.** The restart's
  `(nj=1, ni=235160)` shape implies a `(nj_orig, ni_orig)`
  reshape, but `nj_orig * ni_orig = 235160`. With a CICE grid file
  in hand, the grid file's `(nj, ni)` provides the target shape
  directly and reshape is straightforward. Without one, we cannot
  recover the 2-D structure. Mitigation: cycle 9 only supports
  the paired-with-grid case; the bare-history case returns
  `mesh_pairing_required`. No auto-inference attempted.

- **EAMxx physics-grid file location varies by run.** Some E3SM
  runs put the scrip file alongside outputs; others stash it in a
  per-machine `inputdata/` tree. Heuristic candidate-search may
  surface zero candidates if the grid file isn't sibling to the
  history. Mitigation: the candidate list can be empty; the
  ambiguous envelope's `error.message` then asks the user for an
  absolute path.

- **CICE U-grid vs T-grid.** Some restarts ship both `TLAT/TLON`
  and `ULAT/ULON` in the grid file. Velocity variables (`uvel`,
  `vvel`) live on the U grid; thermodynamic variables live on the
  T grid. Cycle 9 picks T as the default for the paired envelope's
  `spatial` block; a follow-on can plumb per-variable grid
  selection.

- **EAMxx dycore detection edge case.** If a user provides a
  *dycore-only* grid file (per-element GLL nodes), our scrip-style
  candidate heuristic will misclassify it as a physics file.
  Mitigation: cycle-9 only matches `lat[ncol]` 1-D arrays; the
  dycore mapping file has `lat[elem, gp, gp]` 3-D arrays, so
  shape-validation rejects it cleanly.

- **Performance on full-resolution `ncol`.** The dogfood file has
  `ncol = 39620` (ne16pg2 ish). Production EAMxx runs use ne30pg2
  (~150k) or ne1024pg2 (~38M). At ne30pg2 scatter is fine; at
  ne1024pg2 datashader-style aggregation is needed. Mitigation:
  cycle 9 ships scatter; the auto-downsample plumbing from cycle 3
  already handles the ne1024 case via point-count thresholds —
  verify the threshold logic kicks in for the unstructured branch.

- **Variable metadata sparsity in CICE.** `cice.nc` has every
  `long_name`, `standard_name`, `units` as `null` (or "MISSING"
  before placeholder normalization). The renderer's title/legend
  fall-backs (set in cycle 3) handle null gracefully, but verify
  in cycle 9's render tests.

## 6. Out-of-scope follow-ons (cycle 10+ candidates)

- **EAMxx dycore spectral-element rendering** (`elem × gp × gp`).
  HOMME-aware reconstruction; significant new code path.
- **Multi-file globbing for unstructured time series** (still
  carrying over from cycle 8 §6).
- **Time-series and profile plots on unstructured grids** (still
  carrying over from cycle 8 §6).
- **Region clipping on unstructured grids** (still carrying over
  from cycle 8 §6).
- **CICE U-grid plotting path** for velocity variables (cycle 9
  defaults to T-grid).
- **`add_region` applier op** (still zero region findings).
- **Auto-derived CICE block reconstruction from namelist metadata**
  (would let bare-history CICE files plot without a separate grid
  file; needs CICE namelist parsing).

## End of spec

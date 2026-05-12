# Cycle-8 Phase A — unstructured-mesh rendering library survey

> Phase A deliverable per cycle-8 spec
> (`docs/specs/2026-05-11-cycle-8-unstructured-mesh-plotting.md`) §1 and §2.1.
> Survey of candidate Python libraries for rendering MPAS-Ocean Voronoi
> meshes (and similar climate-model unstructured grids) to PNG output.
> Validation files on disk:
>
> - `ocean_mesh.nc` (MPAS-Ocean mesh; 7153 cells × 22403 edges × 11550 vertices × 60 levels; `latCell`/`lonCell`/`xCell` + `verticesOnCell`/`cellsOnVertex`)
> - `ocn.hist.0001-02-01_00.00.00.nc` (MPAS-Ocean history; same dims; `Temperature`, `Salinity`, `SshCell`, `LayerThickness`)
> - `cice.nc` (CICE5/6 restart; `ni=235160, nj=1` flattened)
> - `eamxx.nc` (E3SM EAMxx restart; dual-grid: `ncol=39620` physics + spectral element `elem×gp×gp`)

## TL;DR

**Primary: uxarray.** Only candidate with native MPAS-convention
support and a built-in mesh+history two-file load API
(`ux.open_mfdataset(grid_filename_or_obj, paths)`) — exactly the
shape cycle-8 Phase B §3.3 needs. xarray-native (`UxDataset`
inherits from `xarray.Dataset`), terminates in
matplotlib/holoviews+cartopy with PNG output. Monthly releases
through April 2026, NSF + DOE funded, validated at 84M nodes.

**Secondary fallback: matplotlib `tripcolor` + `mpas_tools.viz.mesh_to_triangles`.**
Zero new heavy dependencies — matplotlib + cartopy are already in
the cycle-5 installer; `mpas_tools` is small. ~25 lines of user
code via the `mesh_to_triangles` helper. Best fit at the
7k-cell dogfood scale; bound at ~500k cells before tripcolor
slows. This is the "thin path" — if uxarray's install footprint
becomes a deal-breaker for cycle-5's installer budget, this is the
viable plan B.

**Scaling fallback: datashader.** First-class `Canvas.trimesh()`
with a numba-JIT'd rasterizer designed for millions of points.
Output is PIL, not matplotlib Figure — adapter glue needed to
match cycle-2's `render_map` contract. No native cartopy; manual
reprojection or GeoViews wrapper. Keep ready for the 1M+ cell
case spec §5 flags as an open risk.

**Disqualified.**

- **PyVista** — 3-D engine. No cartopy CRS layer (no
  PlateCarree/Robinson/Orthographic globe projections). VTK
  install footprint (~50–80 MB wheel) triggers spec §4.8's
  `--no-unstructured` opt-out before any benefit lands.
- **hvplot / holoviews** — no native unstructured primitive; wraps
  datashader's `TriMesh` underneath while adding Bokeh's HTML
  output path. PNG export requires Selenium+Chromium in headless
  contexts. More wrapping, no semantic gain.
- **`xarray-mpas`** (named in spec §2.1) — **does not exist as a
  standalone package on PyPI or GitHub as of May 2026.** Closest
  matches: (a) `pwolfram/mpas_xarray` (long-deprecated; the README
  says "superseded by MPAS-Dev/MPAS-Analysis"), (b)
  `MPAS-Dev/MPAS-Analysis` (full diagnostic framework, not a
  renderer, heavy compset-specific dep stack), (c) uxarray (where
  the xarray+MPAS community converged). Recommendation: remove
  from candidate list in spec §2.1; uxarray is what was meant.

## Per-candidate evaluation matrix

| Dimension | uxarray | matplotlib `tripcolor` + `mpas_tools` | datashader | PyVista | hvplot/holoviews | xarray-mpas |
|---|---|---|---|---|---|---|
| Native unstructured primitives | Voronoi (primal) + Delaunay (dual) via `open_grid(..., use_dual=...)` | `tripcolor` (triangulated) + `PolyCollection` (N-sided polygons) | `Canvas.trimesh(vertices, triangles)` + numba Pineda rasterizer | VTK `UnstructuredGrid` — caller hand-builds from MPAS dims | None native; drops to datashader/holoviews `TriMesh` underneath | n/a (package doesn't exist) |
| MPAS-convention aware (`latCell`, `verticesOnCell`) | **Yes** — UGRID encoding auto-applied | No, but `mpas_tools.viz.mesh_to_triangles` is the standard MPAS-community helper | No — caller fans `verticesOnCell` into triangles manually | No | No | — |
| xarray-native data model | **Yes** — `UxDataset(xarray.Dataset)` | numpy arrays — caller pulls via `.values` | DataFrame for trimesh; xarray for quadmesh/raster | Indirect via alpha `pyvista-xarray` (rectilinear/structured only) | Mixed (xarray for quadmesh; pandas/GeoPandas elsewhere) | — |
| Multi-file mesh+history pairing | **First-class** — `open_mfdataset(grid_filename_or_obj, paths)` | Caller wires (spec §3.3 already plans `paths/mesh_pair.py`) | Caller wires | Caller wires | n/a | — |
| Render output | matplotlib Figure / holoviews + cartopy → PNG via `hv.save` or `fig.savefig` | matplotlib Figure → `fig.savefig('out.png')` (matches existing `render_map`) | PIL via `tf.shade(...).to_pil()` — adapter needed | PNG via `Plotter.screenshot()` (off-screen render) | Bokeh (HTML) default; PNG needs `backend='matplotlib'` AND Selenium+Chromium | — |
| Cartopy compat | Direct — examples pass `ccrs.PlateCarree()`/`Robinson()` to plot calls | First-class — `ax = subplot(projection=ccrs.Robinson())` + `transform=ccrs.PlateCarree()` is the standard idiom metplot already uses | None native — manual reproject or GeoViews wrapper | **None** — disqualifier for global-map use case | Via GeoViews dep (~30 MB more) | — |
| Install footprint | Heavy *list* (cartopy, datashader, geoviews, holoviews, hvplot, numba, dask, geopandas, shapely, scipy, scikit-learn, polars, pyarrow, spatialpandas, pyproj, healpix, antimeridian) — **no VTK** | **Zero new heavy deps** — matplotlib + cartopy already shipped; `mpas_tools` is small (BSD-3) | numba (~40 MB w/ LLVM), pillow, colorcet, dask optional. ~80–120 MB | VTK (~50–80 MB) + Mesa/X11 for off-screen | hvplot + holoviews + bokeh + panel + (opt) geoviews + datashader. ~150–250 MB | — |
| Latest release / cadence (May 2026) | v2026.04.1 (2026-04-23), monthly cadence | matplotlib perpetual; `mpas_tools` BSD-3, MPAS-Dev maintained, 2026 release | v0.19.0 (2026-03-20), healthy HoloViz cadence | v0.48.0 (2026-05-02), 6 releases / 6 months | hvplot v0.12.2 active | — |
| License | Apache-2.0 | matplotlib PSF-style + `mpas_tools` BSD-3 | BSD-3 | MIT | BSD-3 | — |
| Maintainer signal | NSF Project Raijin + DOE SEATS; institutional (NCAR / Penn State / Argonne / UC Davis / LLNL). 2721 commits. **Low churn risk.** | matplotlib upstream perpetual; MPAS-Dev community | HoloViz consortium | Volunteer but extremely active (5928 commits, 82+ releases) | HoloViz consortium | — |
| Perf at 1M+ cells | Documented at 3.75km MPAS-A — **84M nodes / 42M faces**; ~7s grid attach, ~35s render. Comfortably inside spec's <30s for 1M cells threshold. | tripcolor handles ~100–500k triangles OK; 1M-cell MPAS (≈6M tris after fan) gets slow (>30s) and memory-hungry | **Designed for this** — numba'd rasterizer for millions of points; spec §5 explicitly names datashader as the scaling fallback | Strong (VTK underneath); 10M+ cells interactive | Inherits datashader perf when routed through it | — |
| Code volume for the dogfood PoC | ~5–10 lines (`open_mfdataset` → `.isel(Time=0, nVertLevels=0).plot(...)` → `hv.save`) | ~25 lines (mesh_to_triangles helper + tri.Triangulation + tripcolor + savefig) | ~40–60 lines (manual triangle fan + vertices DF + Canvas + shade + PIL save + matplotlib wrapping) | "Build the mesh by hand" — no MPAS-aware helper | More glue than datashader alone | — |

## Per-candidate detail

### 1. uxarray — primary recommendation

- Repo: https://github.com/UXARRAY/uxarray
- Latest: v2026.04.1 (2026-04-23). Monthly cadence (v2026.04.0, v2026.03.0, v2026.02.0, v2025.12.0, v2025.11.0).
- 2721 commits; NSF Project Raijin + DOE SEATS funded; institutional maintainers across NCAR / Penn State / Argonne / UC Davis / LLNL.

**Why primary.** `UxDataset` inherits from `xarray.Dataset`. The
mesh+history two-file API `ux.open_mfdataset(grid_filename_or_obj, paths)`
is exactly cycle-8 §3.3's contract: the inspect tool's new
`mesh_path` parameter maps 1:1 to this signature. MPAS conventions
(`latCell`, `lonCell`, `verticesOnCell`, `cellsOnVertex`) are parsed
and encoded into UGRID automatically — no caller-side fanout. Output
is matplotlib/holoviews + cartopy; PNG via `hv.save(plot, "out.png")`
or `fig.savefig`. Cartopy projections work directly (`ccrs.PlateCarree()`,
`Robinson()`, `Orthographic()` all demonstrated in the plotting docs).

**End-to-end (dogfood path).**

```python
import uxarray as ux
import cartopy.crs as ccrs
import holoviews as hv

uxds = ux.open_mfdataset("ocean_mesh.nc", "ocn.hist.0001-02-01_00.00.00.nc")
surf = uxds["Temperature"].isel(Time=0, nVertLevels=0)
plot = surf.plot(projection=ccrs.Robinson(), cmap="thermal")
hv.save(plot, "out.png")
```

**Risks.** Heavy dep list (cartopy, datashader, geoviews, holoviews,
hvplot, numba, dask, geopandas, shapely, scipy, scikit-learn, polars,
pyarrow, spatialpandas, pyproj, healpix, antimeridian). No VTK. The
cycle-5 installer budget needs auditing — `--no-unstructured` opt-out
flag may be needed per spec §4.8.

### 2. matplotlib `tripcolor` + `mpas_tools.viz.mesh_to_triangles` — secondary fallback

- matplotlib: already shipped.
- `mpas_tools`: https://github.com/MPAS-Dev/MPAS-Tools, BSD-3, MPAS-Dev community.
- Helper: https://mpas-dev.github.io/MPAS-Tools/master/visualization.html (`mesh_to_triangles`).
- Pangeo example: https://gallery.pangeo.io/repos/NCAR/notebook-gallery/notebooks/Binderbot-Bug28/mpas/plot_terrain.html

**Why secondary.** Zero new heavy deps. Matches existing `render_map`
output contract exactly (matplotlib Figure → `fig.savefig`). Native
cartopy idiom — `subplot(projection=ccrs.Robinson())` + `transform=ccrs.PlateCarree()`
is what metplot already uses. The `mesh_to_triangles` helper does the
Voronoi-fan-to-triangulation step in one call; user code is ~25 lines.

**End-to-end (dogfood path).**

```python
import xarray as xr
import matplotlib.pyplot as plt
import cartopy.crs as ccrs
from matplotlib.tri import Triangulation
from mpas_tools.viz.mesh import mesh_to_triangles

mesh = xr.open_dataset("ocean_mesh.nc")
hist = xr.open_dataset("ocn.hist.0001-02-01_00.00.00.nc")
tris = mesh_to_triangles(mesh)
# Interpolate Temperature[t=0, surface] to triangle nodes using
# the helper's nodeCellIndices + nodeCellWeights arrays.
field = hist["Temperature"].isel(Time=0, nVertLevels=0).values
node_vals = (field[tris["nodeCellIndices"].values]
             * tris["nodeCellWeights"].values).sum(axis=1)
triangulation = Triangulation(tris["lonNode"], tris["latNode"],
                              triangles=tris["triangles"])
fig, ax = plt.subplots(subplot_kw={"projection": ccrs.Robinson()})
ax.tripcolor(triangulation, node_vals, shading="gouraud",
             transform=ccrs.PlateCarree(), cmap="thermal")
ax.coastlines()
fig.savefig("out.png", dpi=150)
```

**Risks.** Slows past ~500k cells. Datashader is the path beyond
that threshold (cycle 8 §5 risk #4). Date-line wrap on global plots
needs an explicit unwrap pass on `lonVertex` (cycle 8 task).

### 3. datashader — scaling fallback

- Repo: https://github.com/holoviz/datashader
- v0.19.0 (2026-03-20). HoloViz consortium, healthy cadence.

**Why fallback.** Designed for raster aggregation of millions of
points / triangles. The numba'd Pineda algorithm in `Canvas.trimesh()`
is exactly the path cycle 8 §5 flags as the >1M-cell escape hatch.
Output is PIL — adapter glue needed to match cycle-2's PNG path
(or render via matplotlib backend by wrapping the shaded raster
as an `imshow`).

**Why not primary.** No cartopy CRS layer; reprojection is either
manual (transform lon/lat → projection coords before `Canvas`) or
via GeoViews (more deps). PIL output adds an adapter step the
matplotlib path doesn't need. ~40–60 lines of user code for the
dogfood PoC (manual triangle fan from `verticesOnCell`, vertices
DataFrame, triangle-index DataFrame, Canvas + shade + PIL save).

### 4. PyVista — disqualified

- Repo: https://github.com/pyvista/pyvista
- v0.48.0 (2026-05-02), volunteer-maintained but very active (5928 commits).
- MIT.

**Why disqualified.** 3-D engine, not a 2-D cartographer. **No cartopy
CRS layer** — no PlateCarree, Robinson, Orthographic global
projections. Caller would have to implement the projection math
manually to produce a flat global map. Pulls VTK (~50–80 MB wheel
plus Mesa/X11 for headless off-screen render). The cycle-8 deliverable
is a global PNG map; PyVista's strength (interactive 3-D scenes,
volumes, isosurfaces) doesn't pay back the install cost for this use case.

### 5. hvplot / holoviews — disqualified

- Repo: https://github.com/holoviz/hvplot
- v0.12.2 active 2026.

**Why disqualified.** Geographic doc explicitly lists supported plot
types as `points, polygons, paths, image, quadmesh, contour, contourf`
— **no trimesh/Voronoi**. To render unstructured meshes you drop to
holoviews `TriMesh` → datashader underneath; hvplot is then a wrapper
that adds Bokeh idioms but no new primitive. PNG output from default
Bokeh backend requires Selenium+Chromium for headless rasterization
— flaky in agent contexts. Strictly more code than going to datashader
direct.

### 6. `xarray-mpas` — does not exist

The cycle-8 spec §2.1 names `xarray-mpas` as a candidate. **PyPI
and GitHub searches return no `xarray-mpas` package as of May 2026.**

Closest matches:
- **`pwolfram/mpas_xarray`** (https://github.com/pwolfram/mpas_xarray) — `xtime`-decoding + time-series slicing helper; long-deprecated; README explicitly says "superseded by MPAS-Dev/MPAS-Analysis." Never a renderer.
- **`MPAS-Dev/MPAS-Analysis`** — full diagnostic framework, NOT a general renderer; pulls compset-specific stack.
- **uxarray** — what the community actually converged on for the xarray + MPAS niche.

**Action:** patch cycle-8 spec §2.1 candidate list to remove
`xarray-mpas` and note the lineage. (Tracked as a separate task.)

## Coverage map

Per-family rendering coverage of the recommended primary (uxarray)
and secondary (matplotlib tripcolor + mpas_tools):

| Family | Files in dogfood set | uxarray | tripcolor+mpas_tools | datashader (fallback) |
|---|---|---|---|---|
| MPAS-Ocean | `ocean_mesh.nc` + `ocn.hist.*.nc` | **supported (primary)** | supported (~25 LoC user code) | supports at scale |
| MPAS-Atmosphere | (no dogfood file) | supported by inheritance | supported by inheritance | supports at scale |
| MPAS-Seaice | (no dogfood file) | supported by inheritance | supported by inheritance | supports at scale |
| Omega | shares MPAS-Ocean shape (`NCells` uppercase) | supported (post-uppercase-dim normalization) | supported | supports at scale |
| EAMxx physics (`ncol`) | `eamxx.nc` | partial — needs separate `ncol → (lat, lon)` lookup table (no Voronoi connectivity) | partial — `tripcolor` works once `(lon, lat)` per `ncol` is recovered | full — `Canvas.points` is the natural fit |
| EAMxx dycore (`elem × gp × gp`) | `eamxx.nc` | out of scope cycle 8 (HOMME-aware reconstruction) | out of scope | out of scope |
| CICE flattened (`ni, nj=1`) | `cice.nc` | out of scope cycle 8 (needs CICE `grid.nc` file we don't have) | out of scope | out of scope |

Cycle-8 MUST/SHOULD/MAY/OUT grading from spec §1 reconciles cleanly:
- MUST (MPAS-Ocean): uxarray covers; tripcolor covers; either ships.
- SHOULD (EAMxx physics): both paths can be extended once `ncol → (lat, lon)` is recovered from a coord-var lookup. Treat as a stretch task in Phase B.
- MAY (CICE flattened): out of scope cycle 8 unless a CICE grid file appears in the dogfood set.
- OUT (EAMxx dycore): unchanged.

## Recommendation

Build the Phase B render branch on **uxarray** as the primary path.
The mesh+history two-file API is a 1:1 match for cycle 8 §3.3's
contract, the xarray-native data model means the inspect envelope
flows through naturally, and the documented 84M-node performance
puts cycle 8 §5 risk #4 (1M+ cell perf) to bed.

Keep **matplotlib `tripcolor` + `mpas_tools.viz.mesh_to_triangles`** as
a documented secondary path. If uxarray's install footprint creates
real pain for cycle-5's installer budget (a `--no-unstructured` opt-out
isn't enough), the secondary path needs zero new heavy deps and
covers the MUST scope at ~25 LoC of user code.

Drop **PyVista**, **hvplot/holoviews**, and **`xarray-mpas`** from the
candidate list. Issue a small cycle-8 spec amendment to fix
§2.1 accordingly.

## PoC results (2026-05-11)

Three PoC scripts at `.scratch/cycle-8-poc/` (gitignored) — one per
realistically-viable candidate. All three produced recognizable
global MPAS-Ocean surface-temperature maps. PNGs at
`.scratch/cycle-8-poc/out-*.png`.

### Summary

| PoC | Render time | PNG size | LoC | Visual quality | Notes |
|---|---|---|---|---|---|
| `uxarray_poc.py` | 12.1s | 692 KB | ~50 | sharp Voronoi cell mosaic | `open_mfdataset(mesh, hist)` works first-call; `Temperature.to_polycollection()` has an internal np.delete bug as of uxarray v2026.04.1, so the PoC reaches for `uxds.uxgrid.to_polycollection()` + manual `set_array(surf.values)` instead. |
| `tripcolor_poc.py` | 11.6s | 639 KB | ~75 | clean flat-shaded Voronoi polygons | Hand-fanned `verticesOnCell` → `matplotlib.collections.PolyCollection`. Zero new heavy deps. Dateline-wrap mitigation drops 95 cells (1.3%). |
| `datashader_poc.py` | 3.3s rasterize | 422 KB | ~90 | smooth linear-interp gradient | Triangle-fan into `Canvas.trimesh()`. ~3× faster than the matplotlib paths at this scale; PIL output wrapped in `ax.imshow(transform=PlateCarree)` for cartopy axes. Same dateline-wrap mitigation drops 95 cells. |

### Findings carried over into Phase B planning

1. **MPAS-Ocean `lat*` / `lon*` ships in radians** with `units=None`.
   The mesh file's `latVertex`, `lonVertex`, `latCell`, `lonCell`
   all lack a `units` attribute and use the [0, 2π] (lon) / [-π/2,
   π/2] (lat) convention. Any unstructured-spatial extractor in
   cycle 8 §3.2's `extract_unstructured_spatial(...)` MUST detect
   radians by range (`abs(arr).max() <= 2*np.pi + 0.01`) and
   convert to degrees, OR honor an explicit `units="radians"` attr
   when present. The first PoC pass got this wrong (checked only
   `|max| <= π`) and produced a degenerate zero-meridian strip — a
   real failure mode the inspect envelope's spatial-extraction tests
   must cover.

2. **uxarray remaps dim names**. `nCells` → `n_face`, `Time` (mesh)
   stays uppercase, `time` (history) stays lowercase. The
   `NVertLayers` casing (history-side) is preserved. This means
   the cycle 8 §3.3 mesh-pairing tool needs awareness of both the
   raw NetCDF dim names (for backwards-compatible reads through the
   existing inspect envelope) AND uxarray's UGRID-normalized names
   (when the renderer consumes a `UxDataset`).

3. **uxarray history-file dim casing.** The MPAS-Ocean history file
   `ocn.hist.0001-02-01_00.00.00.nc` uses lowercase `time` +
   uppercase `NCells` / `NVertLayers` / `NEdges`. The mesh uses
   lowercase `nCells` / `nVertLevels` / `nEdges`. This asymmetry
   (already noted in cycle 6's `conventions/mpas.py` detection
   work) is real, persistent, and the case-insensitive dim matching
   that cycle 6 shipped is necessary, not nice-to-have.

4. **Dateline-wrap is non-trivial.** Both hand-rolled PoCs drop
   ~1.3% of cells that straddle the antimeridian (lon span > 180°
   in degrees). uxarray handles it transparently — another
   argument for picking it as primary. Phase B's `_render_unstructured_map`
   in the matplotlib fallback path needs an explicit antimeridian
   wrap routine (split each crossing polygon into two pieces with
   wrapped lon).

5. **Render time at 7k cells.** uxarray and tripcolor both spend
   ~11–12s; that's matplotlib's `PolyCollection` rendering
   dominating, not the data-loading or projection step.
   Datashader's numba'd path is ~3.5× faster (3.3s) and will
   diverge much more at higher cell counts. The spec §5 risk #4
   ("Performance on full-resolution meshes") is real but tractable
   — datashader (or uxarray's native datashader backend) is the
   1M-cell escape hatch.

6. **No `units` attr on Temperature.** `hist["Temperature"]` has a
   `units` attr of `"C"` (Celsius) but no `standard_name`. The
   range [-1.72, 29.82] matches sea-water observed range. Cycle 8
   skill-side will need to know that MPAS-Ocean Temperature is
   `sea_water_conservative_temperature` (TEOS-10) per the cycle-6
   dogfood TEOS-10 finding — that alias mapping is already queued
   as a refinement draft from cycle 6 Phase A.

### Visual confirmation

`out-uxarray.png` (692 KB), `out-tripcolor.png` (639 KB),
`out-datashader.png` (422 KB) — all three show:

- Warm equatorial waters (yellow / 25–30°C)
- Cold polar waters (purple / -2–5°C)
- Land masking (no fill where the MPAS mesh has no cells —
  continents render as the white-background coastlines through)
- Date-line continuity (uxarray) or near-continuity with 1.3%
  cell drop (tripcolor / datashader)

Spec §1 Phase A success criterion #1 — "Does the chosen library
produce a recognizable MPAS-Ocean surface-temperature map?" — is
satisfied for all three viable candidates.

### Recommendation update

The PoCs confirm the survey recommendation: **uxarray as primary,
matplotlib `tripcolor` + hand-rolled unflatten as secondary,
datashader as 1M+ cell scaling fallback.** Phase B can move forward
on uxarray with the secondary path documented as the
`--no-unstructured` opt-out plan for installer-budget constrained
deployments.

## Sources

- [UXarray repo](https://github.com/UXARRAY/uxarray) — primary docs
- [UXarray "Working with MPAS Grids" guide](https://uxarray.readthedocs.io/en/latest/user_guide/grids/mpas.html)
- [UXarray `open_mfdataset` API](https://uxarray.readthedocs.io/en/latest/user_api/generated/uxarray.open_mfdataset.html)
- [UXarray release timeline](https://github.com/UXARRAY/uxarray/releases)
- [Datashader Trimesh user guide v0.19.0](https://datashader.org/user_guide/Trimesh.html)
- [Datashader releases](https://datashader.org/releases.html)
- [matplotlib `tripcolor` docs](https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.tripcolor.html)
- [mpas_tools visualization](https://mpas-dev.github.io/MPAS-Tools/master/visualization.html)
- [MPAS-Tools PR #319 — `mesh_to_triangles`](https://github.com/MPAS-Dev/MPAS-Tools/pull/319)
- [Pangeo Gallery — Plot MPAS data using Delauney Triangulation](https://gallery.pangeo.io/repos/NCAR/notebook-gallery/notebooks/Binderbot-Bug28/mpas/plot_terrain.html)
- [PyVista repo](https://github.com/pyvista/pyvista) — release v0.48.0
- [hvPlot Geographic Data guide](https://hvplot.holoviz.org/user_guide/Geographic_Data.html)
- [hvPlot save API](https://hvplot.holoviz.org/ref/api/generated/hvplot.save.html)
- [`pwolfram/mpas_xarray`](https://github.com/pwolfram/mpas_xarray) — deprecated; "superseded by MPAS-Dev/MPAS-Analysis"

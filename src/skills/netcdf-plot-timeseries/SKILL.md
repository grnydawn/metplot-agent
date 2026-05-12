---
name: netcdf-plot-timeseries
description: Generate a 1D time series plot from a NetCDF variable, optionally area-averaged over a region or extracted at a single point. Handles unit conversion, time aggregation (raw / monthly / annual / seasonal), trendlines, and style-by-reference (extracting visual style from a user-provided reference image). Use whenever the user asks for "X over time", "time series of X", "trend in X", or any 1D plot with time on the x-axis. Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-plot-timeseries

## When to use

Time on the x-axis. Cues: "time series", "over time", "trend", "evolution
of", date range without spatial selection, "monthly", "annual mean".

Even if the user names a region, "X in <region> over time" is a regional
average time series — not a map.

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run, run it now.
2. **Resolve variable name** via aliases.md or `find_variables`.
3. **Resolve spatial reduction:**
   - User gave single (lat, lon) → nearest-neighbor extract (slice with
     point selectors).
   - User gave region → area-weighted average. Use `cos(deg2rad(lat))`
     weighting for rectilinear grids; if the dataset has cell `bounds`
     attributes (CF), prefer bounds-based weights.
   - No spatial constraint and variable has lat/lon dims → area-weighted
     global mean.
   - Variable already 1D in time → use as-is.
4. **Resolve time range** via `find_time` if user named informally
   (default: full record).
5. **Decide aggregation** from request:
   - "monthly mean" / "monthly" → `aggregation="monthly"`
   - "annual mean" / "yearly" → `aggregation="annual"`
   - "seasonal" / "DJF/MAM/JJA/SON" → `aggregation="seasonal"`
   - Otherwise → `aggregation="raw"`
6. **Read data** via `netcdf-reader.read_slice(...)` with appropriate
   selectors (region or point).
7. **Compute spatial reduction skill-side**:
   - For regional/global: weighted mean with `cos(deg2rad(lat))`.
   - For single-point: already done by `read_slice` selectors.
8. **Apply unit conversion** if needed (K → °C, etc.) — see
   `netcdf-plot-map/SKILL.md` for the conventions.
9. **Decide trendline:**
   - User asks for "trend" / "fit" → `trendline="linear"` (or "lowess"
     if specifically requested).
   - Otherwise omit.
10. **If user supplied a reference image**, run style-by-reference flow
    (see "Style by reference" section).
11. **Compose render spec** with `series=[{values, time, label, color?}]`
    or sugar `values + time` for single-series.
12. **Call** `plot-renderer.render_timeseries(spec=...)`.
13. **Verify and report.**
14. **If user corrected anything**, log to `.metplot/task-log.jsonl`.

## Spatial-reduction math

For a rectilinear grid with 1D `lat` (in degrees):

```
weights = cos(deg2rad(lat))                      # shape (n_lat,)
weighted_sum_per_t = sum(values * weights[None, :, None], axis=(1, 2))
weight_total       = sum(weights[:, None]
                          * ones_like(lon)[None, :], axis=(0, 1))
mean_per_t         = weighted_sum_per_t / weight_total
```

Skip cells where `values` is NaN (use `np.nansum` and weight-mask the
denominator). Document the resulting `nan_fraction` in the title or chat.

For curvilinear grids (WRF/ROMS): use the dataset's cell-area variable if
present (e.g., `XAREA`), otherwise approximate with `cos(lat) * ΔlatΔlon`
of the curvilinear coords.

## Calendar handling

If the file uses a non-Gregorian calendar (noleap, 360_day) — reported by
`inspect()` — annual aggregation still works (each year has fixed 365 or
360 days). Note the calendar in the chart title or chat reply if it
might mislead the user (e.g., a "30-year noleap mean" loses ~7 days vs
Gregorian).

## Multi-series

If the user asks to compare regions ("compare SST in NA vs TP over time"):
- Make multiple `read_slice` calls — one per region.
- Compute spatial reductions per series.
- Build `series=[{values, time, label}, ...]` with len > 1.
- Renderer auto-emits a legend.

If user asks to compare variables ("compare T2m and SST over time"):
- Same pattern, one series per variable.
- If units differ, the series share an axis — call this out in chat
  ("the y-axis mixes K and °C; consider plotting separately").

## Pitfalls

- **Area-weighting math when grid is non-uniform.** For rectilinear grids
  with constant Δlat, `cos(lat)` weighting is correct. For irregular Δlat
  or curvilinear grids, use cell areas if available.
- **Leap years for annual aggregation.** Under noleap calendar, every
  year has 365 days; standard datetime tools may misrepresent. Use
  cftime-aware grouping (`xarray` does this with `decode_times=True`).
- **Missing data.** Use `np.nanmean`, not `np.mean` — silent NaN
  propagation produces all-NaN output. Report `nan_fraction` from the
  oracle in the chat.
- **Trend lines vs raw values.** When the user says "trend", they may
  mean "show a trendline" OR "show only the trend, removing seasonal".
  Ask if ambiguous. Default: `trendline="linear"` overlaid on the raw
  series.
- **Unit conversion + slice file form.** If the slice file form is used
  (large slice), you cannot convert units skill-side. Either subset to
  fit inline form or skip conversion and note units in the title.

## Style by reference

If the user supplied a reference plot image:
1. Read `docs/style_template_extraction_prompt.md`.
2. Apply your vision capability to the reference image with that prompt;
   produce a `style_template` JSON.
3. Pass it as `style_template` in the render call (renderer applies per
   cycle-2 spec §8). Include `source` provenance.

The relevant template fields for time series are: `colormap_kind`
(rarely used for line plots; only relevant if comparing many series),
`legend_placement`, `gridlines`, `aspect`, `font_scale`, `title_placement`.
Map-specific fields (`projection_family`, `extent_hint`, `colorbar_position`)
are ignored by `render_timeseries`.

## Multi-file unstructured time-series (MPAS/Omega family) — cycle 11

When the user has a directory of monthly history files (e.g.
`ocn.hist.0001-{01..12}-01_00.00.00.nc`) plus the matching mesh
(`ocean_test_mesh.nc`, `*_mesh.nc`, etc.), build the time-series
from the whole run in one shot. Cycle 11 ships the selector
helpers (`find_nearest_cell`, `cells_in_bbox`, `area_weights`)
and the `cell_index` / `cell_indices` plumbing in `read_slice`
that make this a uniform pipeline.

### Step 1 — paired inspect

```
inspect(path="<dir>/ocn.hist.000*-*-01_00.00.00.nc",
        mesh_path="<dir>/ocean_test_mesh.nc")
```

Returns `kind=local_multi`, `spatial.coord_kind=unstructured`,
`time.n=<total months>`, variables tagged `cell_centered`.

### Step 2 — pick the spatial reduction

| Mode | Cell selection | Weighting |
|---|---|---|
| Single cell at (lat, lon) | `find_nearest_cell(mesh_path, lat, lon) → idx` | none |
| Region (bbox) | `cells_in_bbox(mesh_path, lat_min, lat_max, lon_min, lon_max) → idx[]` | `area_weights(mesh_ds, indices=idx[])` |
| Global | all cells (no selector) | `area_weights(mesh_ds)` |

> **Lon convention**: pass the bbox in the mesh's lon convention.
> Inspect the mesh's `spatial.lon_convention` first; Omega ships
> 0..360, so a North-Atlantic bbox is `lon_min=280, lon_max=360`
> (not -80..0). Cross-dateline bboxes work by setting
> `lon_min > lon_max`.

### Step 3 — slice

```
# Single cell, all times, single level
read_slice(glob_path, "Temperature", level=0,
            cell_index=idx, mesh_path=mesh)
  → shape=[12]   # values across the 12 monthly files

# Subset of cells (regional / global)
read_slice(glob_path, "Temperature", level=0,
            cell_indices=idx_list, mesh_path=mesh)
  → shape=[12, len(idx_list)]
```

### Step 4 — skill-side reduction (for region / global)

```
import numpy as np
ws = area_weights(mesh_ds, indices=idx_list)  # raw areas
ws = ws / ws.sum()                              # normalize
series = (values * ws[None, :]).sum(axis=1)   # → shape=[12]
```

### Step 5 — render

```
render_timeseries({
    "values": series.tolist(),
    "time":   resolved_time_axis,   # from inspect's time.range
    "label":  "Temperature (NAtl area-mean, surface)",
    "ylabel": "degree_C",
})
```

### Multi-cell overlay (cycle 13 theme C)

When the user says "compare these N cells on one plot" or "show
me the cells at (lat₁,lon₁), (lat₂,lon₂), …" on an unstructured
mesh, build a multi-series timeseries:

```
import numpy as np
indices = [find_nearest_cell(mesh_ds, lat=la, lon=lo)
            for (la, lo) in user_points]

series = []
for idx, (la, lo) in zip(indices, user_points):
    env = read_slice(glob_path, "Temperature", level=0,
                      cell_index=idx, mesh_path=mesh)
    series.append({
        "values": env["result"]["values"],
        "time":   resolved_time_axis,
        "label":  f"cell {idx} ({la}°, {lo}°)",
    })

render_timeseries({"series": series, "ylabel": "degree_C"})
```

The renderer auto-emits a legend when `series` has more than
one entry; no extra spec fields needed.

### Named-region lookup (cycle 13 theme C)

For region-mean timeseries on unstructured grids, use
`find_region(name)` to resolve the bbox first, then pass it to
`cells_in_bbox` with whatever lon convention the mesh uses.

```
reg = find_region("North Atlantic")
# reg["lon_min"] = -80, reg["lon_max"] = 0 (catalog spelling)
# MPAS / Omega meshes are in 0..360, so shift:
lon_min = reg["lon_min"] % 360
lon_max = reg["lon_max"] % 360
# If lon_min ends up > lon_max, cells_in_bbox treats it as
# a cross-dateline range automatically (cycle 11 plumbing).

cells = cells_in_bbox(mesh_ds,
                      lat_min=reg["lat_min"], lat_max=reg["lat_max"],
                      lon_min=lon_min, lon_max=lon_max)
```

Cross-dateline regions (`North Pacific`, `Tropical Pacific`,
`South Pacific`) have `lon_min > lon_max` in the catalog —
that shape is preserved verbatim and `cells_in_bbox` handles
it via the OR-union path.

### Pitfalls (cycle-11 specific)

- **Bare glob without mesh_path** returns `spatial=null`; can't
  pick cells. Always supply mesh_path for unstructured globs.
- **`areaCell` missing**: `area_weights` falls back to uniform
  weighting; this biases toward high-latitude small cells.
  Surface that as a warning to the user when using a fallback.
- **Cell-axis case asymmetry**: history uses `NCells`, mesh uses
  `nCells`. The cycle-11 `cell_index` plumbing matches
  case-insensitively, so callers don't need to worry — but if
  hand-rolling an `isel`, lowercase the dim name first.
- **Cross-year glob count**: `000*-*-01_*.nc` matches both year
  0001 and year 0002 files. Verify the count matches user
  expectation.
- **Profiles use the same cell_index path** — see
  `netcdf-plot-profile/SKILL.md`.

## Verification

- Output file size > 5 KB.
- Time axis monotonic (renderer verifies; warns otherwise).
- All series have `n_points > 1`.
- Report: variable, units, spatial reduction (point/region/global),
  time range, n_points, min/mean/max.

## Recording lessons

Log to `.metplot/task-log.jsonl` on user corrections:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-timeseries",
  "step": "spatial_reduction_correction",
  "input": "user said: NA timeseries",
  "resolved_initial": "regional area mean over -80..0 lon, 20..70 lat",
  "resolved_final":   "global area mean",
  "via": "user_correction"
}
```

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — for the analogous map flow + style-by-reference details
- `netcdf-plot-router` — disambiguation
- `netcdf-plot-profile` — sibling plot skill
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt

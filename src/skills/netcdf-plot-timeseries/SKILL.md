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

## Multi-file unstructured time-series (MPAS/Omega family) — cycle 10

When the user has a directory of monthly history files (e.g.
`ocn.hist.0001-{01..12}-01_00.00.00.nc`) plus the matching mesh
file (`ocean_test_mesh.nc`, `*_mesh.nc`, etc.), build the
time-series from the whole run in one shot:

1. Inspect the glob with `mesh_path=`:

       inspect(path="<dir>/ocn.hist.*-*.nc",
               mesh_path="<dir>/ocean_test_mesh.nc")

   Returns `kind=local_multi`, `spatial.coord_kind=unstructured`,
   `time.n=<total months>`, and variables tagged
   `cell_centered`.

2. Spatial reduction options:
   - **Single cell**: pick the cell nearest a user-named
     lat/lon via the mesh's `latCell`/`lonCell` (`np.argmin
     ((lat-lat0)**2 + (lon-lon0)**2)`).
   - **Area-weighted mean over a region**: filter cells whose
     `(latCell, lonCell)` fall in the bbox; weight by
     `areaCell` from the mesh (if present) or by `cos(latCell)`.
   - **Global area-weighted mean**: same with no bbox filter.

3. `read_slice` the variable + cell-index → 1-D values across
   all time entries. Pass the slice + the resolved time coord
   to `render_timeseries`.

Pitfalls:
- The bare glob (without `mesh_path`) returns `spatial=null` —
  you can't pick cells without geometry. Always supply mesh_path
  for unstructured glob workflows.
- For large meshes (`n_cells > 100k`) and many timesteps, prefer
  `xr.open_mfdataset` with chunking; the cycle-1 multi-file path
  uses lazy chunks by default.
- Cross-year file naming (`0002-01-01_*.nc`) gets included by
  globs like `000*-*-01_*.nc` — verify the count matches what
  the user expects.

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

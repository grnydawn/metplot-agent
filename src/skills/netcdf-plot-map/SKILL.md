---
name: netcdf-plot-map
description: Generate a 2D lat/lon map from a NetCDF variable. Handles projection, colormap selection, region subsetting, time and level selection, and unit conversion. Use whenever the user asks for a "map", a spatial snapshot, "show me X over <region>", or any horizontal slice of a 2D or higher-dimensional NetCDF variable. Always run netcdf-inspect first if the file hasn't been inspected this session. Defers to netcdf-plot-router for type disambiguation.
---

# netcdf-plot-map

## When to use

A 2D (lat, lon) view of a variable at a single time and (if applicable) a
single vertical level. Phrases that map here: "plot X on a map", "show X
over the Atlantic", "X at 500 hPa", "snapshot of X".

## Quick reference

1. Confirm `netcdf-inspect` has run on this file. If not, run it.
2. Resolve the variable name against the aliases table in the
   `netcdf-inspect` skill (file: `src/skills/netcdf-inspect/references/aliases.md`).
   If still ambiguous, list candidates to the user.
3. Resolve time selection (default: last time step if not specified).
4. Resolve vertical level if variable is 4D.
5. Resolve region (default: global; check `references/regions.md`).
6. Pick projection based on region (see below).
7. Pick colormap based on field character (see below).
8. Decide units (convert K→°C if user didn't specifically ask for K).
9. Call `plot-renderer` MCP `render_map(...)` with resolved spec.
10. Verify output and report min/mean/max for sanity check.

## Projection selection

- Global → `PlateCarree` (cylindrical equirectangular).
- Polar (latitude > 60° involved as a focus) → `NorthPolarStereo` /
  `SouthPolarStereo`.
- Tropical band → `PlateCarree`.
- Regional (single basin, country) → `PlateCarree` is fine; use `LambertConformal`
  for mid-latitude continental regions if the user wants area accuracy.
- User-specified projection always wins.

## Colormap selection

Look at the field character before picking:

| Field character                      | Default colormap |
|--------------------------------------|------------------|
| Anomaly, departure, change, residual | `RdBu_r` (diverging, centered on 0) |
| Temperature absolute                 | `RdYlBu_r`       |
| Precipitation                        | `viridis` or `Blues` (sequential) |
| Wind speed, magnitudes               | `viridis`        |
| Pressure                             | `viridis`        |
| Humidity                             | `BrBG` (diverging) or `Blues` |

Heuristics:
- If user says "anomaly", "departure", "minus climatology", "vs", use a
  diverging colormap and center the scale on zero.
- If the data range straddles zero significantly, consider diverging.
- Otherwise sequential.
- Respect user override always.

## Region resolution

If user names a region, look it up in `src/data/regions.json`. Common
regions (North Atlantic, Tropical Pacific, Arctic, etc.) are pre-defined.
If not found, ask for bounding box.

Always check the file's longitude convention (recorded by netcdf-inspect)
against the region bounds before subsetting:
- File 0–360, region uses negatives (-80 to 0): shift either the data or
  the bounds. The plot-renderer MCP supports both via the `lon_convention`
  argument.

## Unit conversion for display

Default conversions unless the user asks for the original unit:
- K → °C for temperature.
- Pa → hPa for pressure.
- kg m⁻² s⁻¹ → mm/day for precipitation flux.
- m s⁻¹ stays.

State the conversion in the plot title and in the chat reply ("converted
from K to °C").

## Pitfalls

- **Empty slice, blank plot.** If the region/time selection produces an
  empty array, the renderer may emit a blank figure with no error. Check
  the size of the resolved slice before calling render. Verification step
  catches this too.
- **Longitude convention mismatch** (see Region resolution).
- **Staggered grids.** If variable is on a U or V grid (look for
  `coordinates` attribute pointing to staggered coords), interpolate to
  cell centers first via the `netcdf-reader` MCP's `regrid_to_centers`
  tool, or warn the user and plot anyway with a note.
- **CF time decoding failures** (non-standard calendars). The
  netcdf-reader MCP normally handles these; if it returns numeric time
  values, surface a warning rather than guessing.
- **Auto-scale washing out features.** If the field has extreme outliers
  (e.g. one cell with -9e36 leftover from missing-value handling), the
  colormap range gets dominated by the outlier. Use percentile clipping
  (2–98%) for the default range when min/max diverges by more than 6
  orders of magnitude from the median.
- **User says "global" but variable is regional.** The file may not cover
  the globe. Plot what's there and note the actual extent.

## Verification

After rendering, before reporting success:
- Output file exists and size > 5 KB.
- Compute and report: variable, units, time, level (if any), region,
  array shape, min, mean, max, fraction NaN.
- If fraction NaN > 0.5, warn the user — likely a bad selection or
  masked region.
- If min == max (constant field), warn — usually a bug.

Example reply:
> Saved `north_atlantic_sst_2024-09.png` (320 KB).
> Variable: `tos` (sea surface temperature), converted K → °C.
> Time: 2024-09 (monthly mean). Region: -80 to 0 lon, 20 to 70 lat.
> Range: -1.8 / 18.4 / 28.7 °C (min/mean/max). Coverage: 87% (rest masked over land).

## Recording lessons

If the user corrects any choice (colormap, region bounds, projection,
units, level), log to `.ncplot/task-log.jsonl` with `via:
"user_correction"` and the original vs. corrected values. The
`skill-refiner` will surface these as candidate updates to this skill or
to `references/regions.md` (in this skill) or `src/skills/netcdf-inspect/references/aliases.md`.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-router` — disambiguation
- `references/regions.md` — region definitions
- `src/data/colormaps.json` — colormap-by-quantity reference (if installed)

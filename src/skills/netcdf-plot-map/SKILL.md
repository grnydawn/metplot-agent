---
name: netcdf-plot-map
description: Generate a 2D lat/lon map from a NetCDF variable. Handles projection, colormap selection, region subsetting, time and level selection, unit conversion, and style-by-reference (extracting visual style from a user-provided reference image). Use whenever the user asks for a "map", a spatial snapshot, "show me X over <region>", or any horizontal slice of a 2D or higher-dimensional NetCDF variable. Always run netcdf-inspect first if the file hasn't been inspected this session. Defers to netcdf-plot-router for type disambiguation.
---

# netcdf-plot-map

## When to use

A 2D (lat, lon) view of a variable at a single time and (if applicable) a
single vertical level. Phrases that map here: "plot X on a map", "show X
over the Atlantic", "X at 500 hPa", "snapshot of X", "make a map of X".

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run on this file,
   run it now.
2. **Resolve variable name.** Consult the aliases table in the
   `netcdf-inspect` skill (aliases.md in its references folder) for informal
   names. If still ambiguous, call
   `netcdf-reader.find_variables(path, hint)`.
3. **Resolve time selection** via `netcdf-reader.find_time(path, hint)` if
   the user named a date informally. Default: last time step if not specified.
4. **Resolve vertical level** if variable is 4D. Look for the level in
   `inspect()` output (`result.vertical`) and accept user-supplied level
   in original units.
5. **Resolve region.** Look up the region name in
   `references/regions.json` (machine-readable). If not found, fall back to
   `references/regions.md` or ask the user for an explicit bbox. Default:
   global.
6. **Pick projection** based on region (see "Projection selection" below).
7. **Detect field character** from variable name + units + long_name and
   pick a colormap from `references/colormaps.json` (see "Colormap
   selection" below).
8. **Decide unit conversion** (see "Unit conversion for display").
9. **If user supplied a reference image** for style: run the
   style-by-reference flow (see "Style by reference" section).
10. **Read data** via `netcdf-reader.read_slice(path, variable, time=..., level=..., region=...)`.
11. **Compose render spec** with all resolved fields:
    - `slice_ref` (file form) or `values + lat + lon` (inline form, if the
      slice fits in the inline byte cap or a unit conversion is needed)
    - `projection`, `colormap`, `vmin`/`vmax`/`vcenter`/`clip_pct`
    - `title`, `colorbar_label`, `lon_convention`
    - `style_template` if extracted (step 9)
    - `output_path` if user specified one
12. **Call** `plot-renderer.render_map(spec=...)`.
13. **Verify** (see "Verification" below).
14. **Report** to the user with output path, units, range, warnings.
15. **If user corrected anything**, log to `.ncplot/task-log.jsonl`.

## Projection selection

- **Global** (extent covers > 270° lon) → `PlateCarree` (cylindrical equirectangular).
- **Polar** (latitude > 60° involved as a focus) → `NorthPolarStereo` /
  `SouthPolarStereo`.
- **Tropical band** → `PlateCarree`.
- **Regional** (single basin, country) → `PlateCarree` is fine; use
  `LambertConformal` for mid-latitude continental regions if area
  accuracy matters.
- **User-specified projection always wins.**

## Colormap selection

After detecting field character (rules below), look up
`references/colormaps.json`. The JSON is the source of truth.

**Detection rules:**
- Variable name or `long_name` contains "anomaly" / "departure" / "change" /
  "diff" / "minus" → `anomaly`
- Variable name in {tos, sst, tas, t2m, T2, ts, surface_temperature} or units
  in {K, °C, degC} and no anomaly cue → `temperature_absolute`
- Variable name in {pr, tp, RAINNC, RAINC, precip} or units contain
  `kg m-2 s-1`/`mm`/`mm/day` → `precipitation`
- Variable name in {ua, va, u10, v10, U, V, U10, V10, WSPD, ws} or units
  `m s-1` → `wind_speed`
- Units in {Pa, hPa} and no other cue → `pressure`
- Variable name in {hus, q, QVAPOR, huss} → `specific_humidity`
- Variable name in {hur, rh, RH} → `humidity`
- Variable name in {zg, gh, z} → `geopotential_height`
- No match → `default` (viridis)

**User's explicit `colormap=...` always wins.**

## Region resolution

If user names a region:
1. Open `references/regions.json` and look up by name (case-insensitive,
   substring match accepted).
2. Found → use the bbox.
3. Not found → check `regions.md` for human-readable description; if
   still unclear, ask user for an explicit bbox.

Always check the file's longitude convention (recorded by inspect in
`result.spatial.lon_convention`) against the region bounds. The
plot-renderer applies the shift via the `lon_convention` field; you
just need to set that field correctly.

## Unit conversion for display

Default conversions unless the user explicitly asks for the original unit:
- K → °C for temperature: `T - 273.15`
- Pa → hPa for pressure: `P / 100`
- kg m⁻² s⁻¹ → mm/day for precipitation flux: `× 86400`
- m s⁻¹ stays
- m → km for height-based vertical: `× 0.001`

**Implementation note:** Unit conversion happens skill-side, between
`read_slice` and `render_map`. The renderer doesn't do conversion. This
means the slice must be in inline form so the skill can transform values.
If the slice is too large for inline form, either:
- Subset further (smaller region), so it fits inline.
- Skip conversion; pass raw values; note original unit in title and chat.

State the conversion explicitly in the plot title (e.g., "SST (°C, converted
from K)") and in the chat reply ("converted from K to °C").

## Style by reference

If the user supplied a reference plot image (e.g., "make it look like
this", attached image, or path to a saved figure):

1. Read the prompt template at `docs/style_template_extraction_prompt.md`
   (relative to repo root).
2. Apply your vision capability to the reference image with that prompt;
   produce a `style_template` JSON per the schema in the doc.
3. Validate the JSON loosely (must be a dict; unknown fields are accepted).
4. Pass the JSON as `style_template` in the `render_map` spec. Include
   the `source` provenance block:
   ```json
   {
     "image_path": "<user-provided ref>",
     "extracted_by": "<your model id>",
     "extracted_at": "<ISO timestamp>",
     "confidence": 0.0-1.0
   }
   ```
5. The renderer applies the template per cycle-2 spec §8 — explicit
   spec fields override template fields, which override library defaults.

If no reference image: skip this entire flow.

## Pitfalls

- **Empty slice, blank plot.** If the region/time selection produces a
  zero-cell array, the renderer returns `code: ambiguous, subcode: empty_slice`.
  Don't ignore — surface to user and ask for a different region/time.
- **Longitude convention mismatch.** If the file is 0..360 and you're
  asking for a region with negative lons, set `lon_convention: "-180..180"`
  in the spec. Renderer handles the shift.
- **Staggered grids.** If `inspect()` reported `result.staggered_grid: true`
  AND the variable is on U or V grid, call `netcdf-reader.regrid_to_centers`
  first to interpolate to mass points. Otherwise the plot is offset.
- **CF time decoding failures.** The renderer returns numeric times in
  the response if cftime decode failed. Surface the warning rather than
  guessing.
- **Auto-scale washing out features.** If the field has extreme outliers
  (e.g. one cell with -9e36 leftover from missing-value handling), pass
  `clip_pct: [2, 98]` to suppress them. The renderer also auto-clips when
  data spans > 6 orders of magnitude (per cycle-2 spec §7).
- **User says "global" but variable is regional.** The file may not cover
  the globe. Plot what's there and note the actual extent.
- **NaN-only after region subset.** If the region subset is entirely
  masked (e.g., land for an ocean variable), renderer returns
  `code: ambiguous, subcode: all_nan`. Surface to user.

## Verification

After rendering, before reporting success:
- Output file exists and `result.file_size_bytes` > 5 KB.
- `result.oracle.data.nan_fraction < 1.0`.
- `result.oracle.data.plotted_min != result.oracle.data.plotted_max`
  (constant field is suspicious — usually a bug).
- All warnings in the response envelope are surfaced to the user.

Example reply:
> Saved `north_atlantic_sst_2024-09.png` (320 KB).
> Variable: `tos` (sea surface temperature), converted K → °C.
> Time: 2024-09 (monthly mean). Region: -80 to 0 lon, 20 to 70 lat.
> Range: -1.8 / 18.4 / 28.7 °C (min/mean/max).
> Coverage: 87% (rest masked over land).

## Recording lessons

If the user corrects any choice (colormap, region bounds, projection,
units, level), log a `<step>_correction` event to `.ncplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-map",
  "step": "colormap_correction",
  "input": "auto-picked: RdYlBu_r",
  "resolved": "viridis",
  "via": "user_correction",
  "context": {"variable": "tos", "units": "K"}
}
```

Step values: `colormap_correction`, `region_correction`, `projection_correction`,
`level_correction`, `unit_conversion_skipped`. Required fields: `ts`,
`skill`, `step`, `via`. The `skill-refiner` (cycle 6) consumes these.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-router` — disambiguation
- `netcdf-plot-timeseries`, `netcdf-plot-profile` — sibling plot skills
- `references/regions.json`, `references/regions.md` — region definitions
- `references/colormaps.json` — field-character → colormap mapping
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt

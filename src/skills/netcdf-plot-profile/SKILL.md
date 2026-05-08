---
name: netcdf-plot-profile
description: Generate a vertical profile plot (variable vs height/pressure/depth) at a single point or area-averaged. Handles pressure-axis inversion, log-scale for pressure, depth-axis inversion (positive-down), unit conversion, and style-by-reference. Use whenever the user asks for a "profile", "vertical structure", "vertical X", or "X vs height/pressure". Always run netcdf-inspect first if the file hasn't been inspected this session. Cross-section and Hovmöller plots are not yet supported in this cycle — netcdf-plot-router will inform the user when those are requested.
---

# netcdf-plot-profile

## When to use

Vertical structure of a variable at a single location or area average.
Cues: "profile", "vertical X", "X vs height", "X vs pressure", "X at all
levels".

Cross-section (2D slice through a 3D field) and Hovmöller (time vs
spatial axis) are **not supported in this cycle** — `netcdf-plot-router`
informs the user. This skill handles only vertical profile.

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` has not run, run it now.
2. **Resolve variable name** via aliases.md or `find_variables`.
3. **Confirm vertical coordinate present** in `inspect()` output:
   `result.vertical` should be non-null with a `kind` ("pressure", "height",
   "depth", "model_level"). If missing, this isn't a profile-able variable.
4. **Resolve spatial reduction:**
   - User gave single (lat, lon) → nearest-neighbor extract.
   - User gave region → area-weighted average across the region.
   - Default: ask user (point or area? — profiles are usually point-based).
5. **Resolve time selection** (default: last time step). Profiles are
   usually instantaneous.
6. **Read data** via `netcdf-reader.read_slice(...)` with selectors that
   reduce to (vertical, ) — i.e., one value per vertical level.
7. **Apply unit conversion** if needed (K → °C, Pa → hPa, m → km).
8. **Set vertical-axis policy** based on `vertical.kind`:
   - `pressure` (units in {Pa, hPa}) → `vertical_units` = matching unit;
     `log_scale=True`, `invert_pressure=True` (low pressure at top).
   - `height` (units in {m, km}) → `log_scale=False`, `invert_pressure=False`.
     Optional km conversion if range > 1000 m.
   - `depth` (units in {m}) → `log_scale=False`, `invert_pressure=True`
     (deepest at bottom; surface at top).
   - `model_level` (dimensionless) → `log_scale=False`, `invert_pressure=False`.
     Note in title that levels are model levels, not physical units.
9. **If user supplied a reference image**, run style-by-reference flow.
10. **Compose render spec:** `series=[{values, vertical, label, color?}]`
    or sugar `values + vertical` for single-profile. Include
    `vertical_units`, `vertical_axis="y"` (default), `log_scale`,
    `invert_pressure`.
11. **Call** `plot-renderer.render_profile(spec=...)`.
12. **Verify and report.**
13. **If user corrected anything**, log to `.metplot/task-log.jsonl`.

## Multi-profile

If user asks to compare ("compare T profile in NA vs TP"):
- Multiple `read_slice` calls.
- Build `series=[{values, vertical, label}, ...]`.
- Renderer auto-emits a legend.

## Pitfalls

- **Pressure-axis convention.** Atmospheric pressure decreases with
  altitude — top of plot is low pressure (high altitude). The renderer
  honors `invert_pressure=True`; pass it for any pressure-coordinate
  variable.
- **Log scale for full-column pressure.** A profile from 1000 hPa to 10 hPa
  is meaningless on linear y because the atmosphere thins exponentially.
  Default to log scale for pressure (the renderer auto-picks log when
  `vertical_units in {Pa, hPa}` per cycle-2 spec §2.3).
- **Terrain-following coordinates** (sigma, hybrid sigma-pressure). The
  vertical coordinate isn't a clean physical pressure; values vary with
  surface pressure. If `inspect()` reports a hybrid coord, use the
  derived pressure values if the file provides them; otherwise plot
  against the model-level index and note in the title.
- **Depth profiles.** Ocean variables: vertical coord may have
  `positive="down"`. The renderer handles this (uses `invert_pressure`
  semantics — deep at bottom). Verify the deepest values appear at the
  bottom of the plot in the oracle.
- **Mismatched levels across series.** When comparing two profiles, the
  vertical coordinates must align. If they don't, interpolate to a
  common grid skill-side before passing.
- **Cross-section confusion.** If the user says "vertical cross-section",
  defer to `netcdf-plot-router` — that's not a profile in the
  cycle-3 sense.

## Style by reference

If the user supplied a reference plot image:
1. Read `docs/style_template_extraction_prompt.md`.
2. Apply vision; produce `style_template` JSON.
3. Pass it to `render_profile` with `source` provenance.

Relevant template fields: `legend_placement`, `gridlines`, `aspect`,
`font_scale`, `title_placement`. Color/projection fields are
mostly irrelevant for profiles.

## Verification

- Output file size > 5 KB.
- Vertical axis monotonic.
- All series have `n_points > 1`.
- For pressure profiles: oracle's `drawn.log_scale` is True, `drawn.invert_pressure`
  is True.
- Report: variable, units, mode (profile), spatial reduction, vertical
  range, n_levels.

## Recording lessons

Log corrections to `.metplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-plot-profile",
  "step": "vertical_axis_correction",
  "input": "auto-picked: log scale + invert (pressure)",
  "resolved": "linear scale + no invert (per user request)",
  "via": "user_correction",
  "context": {"vertical_units": "hPa"}
}
```

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — sibling plot skill (covers style-by-reference details)
- `netcdf-plot-timeseries` — sibling plot skill
- `netcdf-plot-router` — disambiguation
- `docs/style_template_extraction_prompt.md` — style-by-reference vision prompt

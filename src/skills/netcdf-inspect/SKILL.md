---
name: netcdf-inspect
description: Inspect a NetCDF file before doing anything else with it. Lists variables, dimensions, coordinate ranges, units, and CF metadata. Use this whenever a NetCDF file path is mentioned for the first time in a session, before attempting any plot, slice, or analysis. Also use when the user asks "what's in this file" or "what variables are available". Do NOT skip this step even if the filename suggests what's inside — filenames lie, conventions differ, and grounding every later step in real metadata prevents a large class of silent failures.
---

# netcdf-inspect

## When to use

- Any NetCDF file path appears for the first time in a session.
- User asks what's in a file ("what variables", "show me the structure").
- User asks for a plot/slice from a file you haven't inspected yet — inspect
  first, then proceed.
- Path is local, glob (`*.nc`), remote URL (`https://...`), or SSH
  (`ssh://host/path.nc`). The MCP handles all of these.

## Quick reference

1. Call `netcdf-reader.inspect(path=<path>)`.
2. If the response envelope is `ok: false` with subcode `ssh_auth_needed`,
   prompt the user for SSH credentials per the candidates list, then retry
   with `ssh_config={user, host, port, auth: {...}}`.
3. Read `result.kind`, `result.convention`, `result.variables`,
   `result.dimensions`, `result.spatial`, `result.time`, `result.vertical`.
4. Summarize for the user (see "What to surface" below).
5. Cross-reference variable names against `references/aliases.md` if the
   user's later prompt names a quantity informally.
6. If an alias resolution differs from what the user said, log a
   `alias_correction` event to `.metplot/task-log.jsonl` (see "Recording
   lessons").

## What to surface to the user

Don't dump the entire ncdump output. The user wants:
- **Variables:** number total, with the 5–10 most plot-relevant ones named
  explicitly (prioritize ones with both spatial and temporal dimensions).
- **Time range:** start, end, frequency if regular (use `result.time.range`
  and `result.time.frequency`).
- **Spatial extent:** lon range, lat range, grid resolution (use
  `result.spatial.lon_range`, `result.spatial.lat_range`, and the lon
  convention from `result.spatial.lon_convention`).
- **Vertical coord** if present: kind (pressure / height / depth / model_level)
  and value range (use `result.vertical`).
- **Convention:** primary (`CF` / `WRF` / `ROMS`) plus any candidates if
  ambiguous.
- **Red flags:** see Pitfalls.

## Available helper tools

For follow-up resolution beyond `inspect()`:

- `netcdf-reader.find_variables(path, hint)` — score variables against
  `long_name`/`standard_name`/`description` for fuzzy lookup.
- `netcdf-reader.find_time(path, hint)` — parse "2024-09", "last", "first"
  into ISO + index.

## Pitfalls

- **Longitude convention.** Files are either 0–360 or -180–180. The
  difference is silent until a user names a region — record which one
  this file uses (it's in `result.spatial.lon_convention`).
- **Calendar.** CF supports several non-Gregorian calendars (noleap,
  360_day, julian). The MCP normalizes via cftime, but downstream
  pandas-style tools may fail. Note the calendar in the inspection summary.
- **Staggered grids (WRF).** U and V on different grids than scalars
  (Arakawa C-grid). The MCP detects this and reports
  `result.staggered_grid: true` plus annotated coordinate names. Plotting
  needs interpolation via `netcdf-reader.regrid_to_centers`.
- **Curvilinear coordinates (WRF, ROMS).** 2D `XLAT`/`XLONG` instead of 1D
  `lat`/`lon`. The MCP exposes both via `result.spatial.coordinate_kind`
  ("rectilinear" or "curvilinear"). The renderer handles both.
- **Time as numbers.** Time variable may be `days since 1850-01-01` or
  similar. The MCP decodes via `decode_times=True`; if the response
  contains a `cf_time_decode_failed` warning, surface it.
- **Variables with no `units` attribute.** Common in research output.
  Note this; the plotting skills will need to ask the user.
- **Unstructured grids.** ICON, MPAS, FV3 may use unstructured meshes.
  Detected by absence of regular `lon`/`lat` coordinates. Cycle-3
  doesn't ship plotting for these — surface this and stop.

## Verification

Before declaring inspection complete:
- Confirm at least one variable was returned (`len(result.variables) > 0`).
- Confirm dimension sizes are non-zero.
- Confirm coordinate values are monotonic where expected (lat/lon/time).
  The MCP marks non-monotonic axes in `result.warnings`.
- If any check fails, surface the failure to the user — do not proceed
  to plotting on a malformed file.

## Style by reference

`netcdf-inspect` does not produce plots and does not consume style
templates. (The plot skills handle the style-by-reference flow; see
`netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile`.)

## Recording lessons

If the user corrects you about variable name resolution, append to
`.metplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601 UTC>",
  "skill": "netcdf-inspect",
  "step": "alias_correction",
  "input": "user said: SST",
  "resolved": "tos",
  "via": "user_correction",
  "context": "CMIP6 historical run"
}
```

Required fields: `ts`, `skill`, `step`, `via`. `input`, `resolved`, and
`context` are recommended.

The `skill-refiner` (cycle 6) will pick this up at session end and
propose adding the alias to `references/aliases.md`.

## See also

- `netcdf-plot-router` — what to do after inspection
- `netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile` — produce plots
- `references/aliases.md` — variable name aliases
- `references/conventions.md` — CF conventions cheat sheet

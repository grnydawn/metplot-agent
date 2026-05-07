---
name: netcdf-inspect
description: Inspect a NetCDF file before doing anything else with it. Lists variables, dimensions, coordinate ranges, units, and CF metadata. Use this whenever a NetCDF file path is mentioned for the first time in a session, before attempting any plot, slice, or analysis. Also use when the user asks "what's in this file" or "what variables are available". Do NOT skip this step even if the filename suggests what's inside — filenames lie, conventions differ, and grounding every later step in real metadata prevents a large class of silent failures.
---

# netcdf-inspect

## When to use

- Any NetCDF file path appears for the first time in a session.
- User asks what's in a file.
- User asks for a plot/slice from a file you haven't inspected yet — inspect
  first, then proceed.

## Quick reference

1. Call the `netcdf-reader` MCP `inspect(path)` tool.
2. Summarize: variable list with shapes, dimension ranges, time span,
   spatial extent, CF conventions, any unusual things (staggered grids,
   non-standard calendars, missing units).
3. Cache the result in `.ncplot/inspections/<file-hash>.json` so other
   skills in the session can read it without re-calling the MCP.
4. Cross-reference variable names against `references/aliases.md` — if a
   user later says "SST" or "temperature", you'll know the actual variable
   name in this file.

## What to surface to the user

Don't dump the entire ncdump output. The user wants:
- Number of variables, with the 5–10 most plot-relevant ones named explicitly.
- Time range (start, end, frequency if regular).
- Spatial extent (lon range, lat range, grid resolution).
- Vertical coordinate if present (pressure levels, model levels, depth).
- Any red flags (see Pitfalls).

## Pitfalls

- **Longitude convention.** Files are either 0–360 or -180–180. The
  difference is silent until a user names a region — record which one
  this file uses.
- **Calendar.** CF supports several non-Gregorian calendars (noleap,
  360_day, julian). Standard pandas datetime conversion fails on these.
  Note the calendar in the inspection summary.
- **Staggered grids.** Some weather/climate models output U and V on
  different grids than scalars (Arakawa C-grid). Look for separate
  `lon_u`, `lat_v` etc. coordinates. Plotting needs interpolation.
- **Time as numbers.** Time variable may be `days since 1850-01-01` or
  similar. Decode using the CF `units` and `calendar` attributes. The
  netcdf-reader MCP does this automatically; double-check the result.
- **Variables with no `units` attribute.** Common in research output. Note
  this; the plotting skills will need to ask the user.
- **Unstructured grids.** ICON, MPAS, and FV3 may use unstructured meshes.
  Detected by the absence of regular `lon`/`lat` 1D coordinates. Different
  plotting path required.

## Verification

Before declaring inspection complete:
- Confirm at least one variable was returned.
- Confirm dimension sizes are non-zero.
- Confirm coordinate values are monotonic where expected (lat/lon/time).
- If any check fails, surface the failure to the user — do not proceed
  to plotting on a malformed file.

## Recording lessons

If the user corrects you about variable names, conventions, or
peculiarities of this kind of file, log to `.ncplot/task-log.jsonl`:

```json
{
  "ts": "<iso8601>",
  "skill": "netcdf-inspect",
  "step": "alias_correction",
  "input": "user said: SST",
  "resolved": "tos",
  "via": "user_correction",
  "context": "CMIP6 historical run"
}
```

The `skill-refiner` will pick this up at session end and propose adding
the alias to `references/aliases.md`.

## See also

- `references/aliases.md` — variable name aliases
- `references/conventions.md` — CF conventions cheat sheet
- `netcdf-plot-router` — what to do after inspection

---
name: netcdf-plot-router
description: Decide which plot type to make from a free-form natural-language request and dispatch to the right plotting skill. Use this whenever the user asks to plot, show, visualize, or graph something from a NetCDF file but hasn't specified the plot type explicitly. Covers maps, time series, vertical profiles, cross-sections, and Hovmöller diagrams. If the request is ambiguous (e.g. "show me SST"), this skill asks one clarifying question; if it's clear, it dispatches without prompting. Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-plot-router

## When to use

User wants a plot from a NetCDF file but didn't specify which plot type, or
the type is implied but you want to confirm.

## Decision tree

1. Has the file been inspected this session? If no → run `netcdf-inspect`.
2. Look at the user's request for plot-type cues:

   | Cue                                        | Skill                       |
   |--------------------------------------------|-----------------------------|
   | "map", "spatial", named region, projection | `netcdf-plot-map`           |
   | "time series", "over time", date range     | `netcdf-plot-timeseries`    |
   | "vertical", "profile", pressure level dim  | `netcdf-plot-profile`       |
   | "cross-section", "transect"                | `netcdf-plot-profile` (cross-section mode) |
   | "Hovmöller", "lat-time", "lon-time"        | `netcdf-plot-profile` (hovmoller mode) |
   | none of the above, but variable is 2D (lat,lon) at one time → assume map |

3. If still ambiguous, ask **one** question:

   > "I can show that as a map, a time series, or a vertical profile —
   > which one?"

   Don't list every possible variant. Two or three options max.

4. Once decided, load the relevant skill and pass along:
   - file path
   - resolved variable name (from inspect step)
   - any region / time / level constraints already in the request

## Pitfalls

- Don't ask the type question if the answer is obvious. "Plot SST in the
  North Atlantic for September" is unambiguously a map. Asking is friction.
- "Over time" in the request always means time series, even if a region is
  also named (it's a regional average time series).
- "At 500 hPa" plus a region and time means a map at that level, not a
  profile.
- "Profile" without context usually means vertical profile (single point
  or area-averaged).

## Verification

- Confirm a sub-skill was actually invoked.
- Confirm the sub-skill received a resolved variable name, not the user's
  original informal name.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — 2D maps
- `netcdf-plot-timeseries` — 1D time series
- `netcdf-plot-profile` — vertical, cross-section, Hovmöller

---
name: netcdf-plot-router
description: Decide which plot type to make from a free-form natural-language request and dispatch to the right plotting skill. Use this whenever the user asks to plot, show, visualize, or graph something from a NetCDF file but hasn't specified the plot type explicitly. Covers maps, time series, and vertical profiles. Cross-section and Hovmöller plots are not yet supported (deferred to a later cycle); this skill informs the user when those are requested.
---

# netcdf-plot-router

## When to use

User wants a plot from a NetCDF file but didn't specify which plot type, or
the type is implied but worth confirming.

## Quick reference

1. Has the file been inspected this session? If no → run `netcdf-inspect`
   first. Don't proceed without inspection — most ambiguities resolve
   themselves once you know what's in the file.

2. Apply the decision tree below to the user's request:

   | Cue                                                         | Skill / action                                          |
   |-------------------------------------------------------------|---------------------------------------------------------|
   | "map", "spatial", named region, projection, "show X over R" | invoke `netcdf-plot-map`                                |
   | "time series", "over time", "trend", "evolution of X"       | invoke `netcdf-plot-timeseries`                         |
   | "vertical", "profile", multiple levels at single point/area | invoke `netcdf-plot-profile`                            |
   | "cross-section", "transect"                                 | **deferred** — see "Deferred plot types" below          |
   | "Hovmöller", "lat-time", "lon-time", "time-longitude"       | **deferred**                                            |
   | Variable shape (lat,lon) at one time, no other cues         | invoke `netcdf-plot-map` (default for 2D spatial)       |

3. If still ambiguous after the decision tree, ask **one** clarifying
   question with 2–3 options. Don't list every variant.

   > "I can show that as a map, a time series, or a vertical profile —
   > which one?"

4. Once decided, invoke the matched skill, passing along:
   - file path
   - resolved variable name (from inspect step)
   - any region / time / level constraints already in the request
   - reference image path/URL if user provided one (for style-by-reference)

## Deferred plot types

Cross-section and Hovmöller plots are not supported in the current
release. When detected, respond:

> "Cross-section plots (a 2D slice through a 3D field) and Hovmöller
> diagrams (time vs spatial axis) aren't supported yet — they're queued
> for a future release. Right now I can do maps, time series, and vertical
> profiles. Would any of those work for what you have in mind?"

Don't try to fake it (e.g., averaging until a profile-like shape emerges
without warning the user) — that produces a misleading plot.

## Pitfalls

- **Don't ask the type question if the answer is obvious.** "Plot SST in
  the North Atlantic for September" is unambiguously a map. Asking is
  friction.
- **"Over time" always means time series**, even if a region is also named
  (it's a regional average time series).
- **"At 500 hPa" + region + time** means a map at that level, not a
  profile. Profiles are 1D in vertical.
- **"Profile" without context** usually means vertical profile (single
  point or area-averaged). Ask if ambiguous.
- **Variable shape doesn't override explicit cue.** If user says "time
  series of T2", even though T2 is a 2D field, do a single-point or
  area-mean time series — not a map.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-map` — 2D maps
- `netcdf-plot-timeseries` — 1D time series
- `netcdf-plot-profile` — vertical profile

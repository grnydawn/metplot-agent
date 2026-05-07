---
name: netcdf-plot-timeseries
description: Generate a 1D time series plot from a NetCDF variable, optionally area-averaged over a region or extracted at a single point. Use whenever the user asks for "X over time", "time series of X", "trend in X", or any 1D plot with time on the x-axis. Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-plot-timeseries

> **Status: scaffold.** Structure and key decisions are listed; full procedure
> needs implementation. Use `netcdf-plot-map` as a reference for the level of
> detail expected.

## When to use

Time on the x-axis. Cues: "time series", "over time", "trend", "evolution
of", date range without spatial selection, "monthly", "annual mean".

## Quick reference

1. Confirm `netcdf-inspect` has run.
2. Resolve variable name.
3. Resolve spatial reduction:
   - single point (lat, lon given) → nearest-neighbor extract
   - region given → area-weighted average (use `cos(lat)` weighting, or
     bounds-based if `bounds` attributes are present)
   - global → area-weighted global mean
4. Resolve time range (default: full record).
5. Optional time aggregation: monthly, annual, seasonal mean.
6. Call `plot-renderer` MCP `render_timeseries(...)`.
7. Verify and report.

## Pitfalls

- TODO: area-weighting math when grid is non-uniform.
- TODO: handling of leap years for annual aggregation under noleap calendar.
- TODO: missing data — np.nanmean vs np.mean changes the answer materially.
- TODO: trend lines vs raw values — what does the user want?

## Verification

- Output file size > 5 KB.
- Time axis monotonic.
- Report: variable, units, spatial reduction, time range, n_points.

## See also

- `netcdf-plot-map` — for the analogous map flow
- `netcdf-plot-router` — disambiguation

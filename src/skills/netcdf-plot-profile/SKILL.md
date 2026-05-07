---
name: netcdf-plot-profile
description: Generate vertical profiles (variable vs height/pressure), cross-sections (variable on a 2D slice through a 3D field), and Hovmöller diagrams (variable vs time on one spatial axis). Use whenever the user asks for a "profile", "vertical structure", "cross-section", "transect", "Hovmöller", or "lat-time" / "lon-time" plot. Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-plot-profile

> **Status: scaffold.** Structure and key decisions are listed; full procedure
> needs implementation. Use `netcdf-plot-map` as a reference for the level of
> detail expected.

## When to use

Three related plot types share enough machinery to live in one skill:

- **Vertical profile** — variable on the y-axis, vertical coord (pressure,
  height, depth) on the x-axis or vice versa. Single point or area mean.
- **Cross-section** — 2D slice through a 3D field, e.g. lat-pressure or
  lon-pressure. One spatial axis collapsed.
- **Hovmöller** — time vs one spatial axis (lat-time or lon-time), the
  other axis collapsed by averaging.

## Quick reference

1. Confirm `netcdf-inspect` has run.
2. Resolve which sub-mode based on user phrasing:
   - "profile" → vertical profile
   - "cross-section", "transect" → cross-section
   - "Hovmöller", "lat-time", "lon-time", "time-longitude" → hovmoller
3. For vertical profiles: pressure axis usually inverted (top of atmosphere up).
4. For pressure as vertical: use log scale by default for full atmospheric column.
5. Call `plot-renderer` MCP with the appropriate `render_profile`,
   `render_cross_section`, or `render_hovmoller` tool.
6. Verify and report.

## Pitfalls

- TODO: pressure axis convention (decreasing upward).
- TODO: terrain following coords (sigma, hybrid sigma-pressure).
- TODO: cross-section interpolation for non-axis-aligned transects.
- TODO: Hovmöller with non-equal-area averaging.

## Verification

- Output file size > 5 KB.
- Vertical or time axis monotonic.
- Report: variable, units, mode (profile/cross/hov), reduction, n_points.

## See also

- `netcdf-plot-map`, `netcdf-plot-timeseries`
- `netcdf-plot-router`

# plot-renderer MCP server

Renders matplotlib/cartopy figures from structured plot specs.
Doesn't know about NetCDF — pure rendering.

## Tools exposed

### `render_map(spec: dict) -> dict`
Render a 2D lat/lon map. Spec fields:
- `values` (2D array or path to npz/temp file)
- `lon`, `lat` (1D arrays)
- `projection` (`PlateCarree`, `Robinson`, `NorthPolarStereo`, ...)
- `extent` (lon_min, lon_max, lat_min, lat_max) — optional
- `lon_convention` (`-180..180` or `0..360`) — for shift handling
- `colormap` (`viridis`, `RdBu_r`, ...)
- `vmin`, `vmax`, `clip_pct` (e.g. [2, 98] for percentile clipping)
- `title`, `colorbar_label`
- `output_path`, `dpi`, `format` (png/pdf/svg)

Returns: `{output_path, file_size_bytes, plotted_min, plotted_max}`.

### `render_timeseries(spec: dict) -> dict`
- `values` (1D array), `time` (datetime array)
- `aggregation` (raw / monthly / annual / seasonal)
- `trendline` (None / linear / lowess)
- `title`, `ylabel`, `output_path`, `dpi`, `format`

### `render_profile(spec: dict) -> dict`
Vertical profile: variable on one axis, vertical coord on the other.
- `values`, `vertical_values`, `vertical_units` (Pa, hPa, m, km)
- `vertical_axis` (x or y), `log_scale` (bool, default true for atmosphere)
- `invert_pressure` (default true)
- `title`, `output_path`, `dpi`, `format`

### `render_cross_section(spec: dict) -> dict`
2D field with one spatial and one vertical axis.

### `render_hovmoller(spec: dict) -> dict`
2D field with time on one axis, lat or lon on the other.

## Dependencies

- `matplotlib`, `cartopy`, `numpy`
- `mcp`

## Implementation status

Stub. `server.py` defines tool signatures.

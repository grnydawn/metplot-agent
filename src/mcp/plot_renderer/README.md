# plot-renderer MCP server

Renders matplotlib/cartopy figures from structured plot specs.
Doesn't know about NetCDF — pure rendering.

## Tools

### `render_map(spec)`

Render a 2D lat/lon map. See spec §2.1 for full field list.

Key spec fields: `values + lat + lon` (inline) OR `slice_ref` (file
form), `projection`, `colormap`, `vmin/vmax/clip_pct`, `vcenter`,
`title`, `colorbar_label`, `lon_convention`, `style_template`,
`output_path`, `dpi`, `format`, `downsample`.

Returns: `{output_path, file_size_bytes, plotted_min, plotted_max,
plotted_shape, applied_downsample, applied_lon_shift, nan_fraction,
oracle}`.

Ambiguity envelopes: `cartopy_missing`, `unknown_colormap`,
`unknown_projection`, `empty_slice`, `all_nan`.

### `render_timeseries(spec)`

1D time series, single or multi (`series=[{values, time, label, color?}, ...]`).
Sugar `values+time` accepted for single-series. Optional `aggregation`,
`trendline` (`null|linear|lowess`), `style_template`. See spec §2.2.

### `render_profile(spec)`

Vertical profile. `series=[{values, vertical, label, color?}, ...]` plus
`vertical_units` (Pa/hPa/m/km), `vertical_axis` (x/y), `invert_pressure`,
`log_scale`. See spec §2.3.

## Envelope shape

Same as cycle-1's `netcdf-reader`:

```
{ok: true,  result: {...}, warnings: [...]}
{ok: false, error: {code, message, context}}
{ok: false, error: {code: "ambiguous", subcode, candidates, retry_with_param}}
```

## Output management

Figures default to `.metplot/figures/{tool}_{var}_{when}_{hash6}.{format}`
unless `output_path` is supplied. Figures are persistent; the directory
is never auto-cleaned.

## Style by reference

Pass `style_template` (a JSON dict per spec §8) to apply look-and-feel
from a reference plot. Cycle-3 skills supply the dict by asking the
host LLM to extract it from a user-supplied image; cycle-2 stays
deterministic. See `docs/style_template_extraction_prompt.md`.

## Install

```bash
uv pip install -e src/mcp/plot_renderer
# Optional:
uv pip install cartopy   # for render_map
uv pip install scipy     # for trendline=lowess
```

## Implementation status

Implemented per `docs/plans/2026-05-07-cycle-2-plot-renderer.md`. Full
test suite under `tests/mcp/plot_renderer/`. Image-diff suite is
opt-in (`pytest --image-diff`).

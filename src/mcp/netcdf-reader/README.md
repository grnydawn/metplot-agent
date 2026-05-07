# netcdf-reader MCP server

Provides NetCDF inspection and slicing tools to AI agents.

## Tools exposed

### `inspect(path: str) -> dict`
Open a NetCDF file and return a structured summary:
- variables: list of {name, dims, shape, dtype, units, long_name}
- coords: list of coordinate variables with ranges
- dims: dimension sizes
- time: parsed range, frequency, calendar
- spatial: lon/lat extent and resolution, longitude convention (0..360 vs -180..180)
- vertical: levels with units if present
- attrs: global attributes
- warnings: list of any anomalies (non-monotonic coords, missing units, etc.)

Cached: subsequent `inspect()` calls on the same path read from
`.ncplot/inspections/<file-hash>.json`.

### `read_slice(path: str, variable: str, **selection) -> dict`
Return a numerical slice as a structured payload:
- selection kwargs: `time`, `level`, `lat`, `lon` (single value, slice, or list)
- region: optional named region (resolved against `regions.json`)
- regrid: optional, "centers" to interpolate staggered to cell centers
- returns: `{values, coords, units, dims, fill_value}` — values is a JSON-safe
  nested array (or a path to a temp file for large slices).

### `compute_stats(path: str, variable: str, **selection) -> dict`
Cheap summary stats over a (sub)slice without returning the full array:
- min, max, mean, std, fraction_nan, n_points
- used by plotting skills for sanity-check reporting.

### `regrid_to_centers(path: str, variable: str, **selection) -> dict`
For staggered-grid variables (Arakawa C-grid U/V), interpolate to cell centers.
Returns the same payload shape as `read_slice`.

## Dependencies

- `xarray` (with `netcdf4` and `cftime`)
- `numpy`
- `mcp` (MCP server SDK)

## Running standalone

```bash
python -m mcp.netcdf_reader.server
```

Or via the MCP launch stanza emitted by each target builder.

## Implementation status

Stub. `server.py` defines the tool signatures; the bodies are TODO.

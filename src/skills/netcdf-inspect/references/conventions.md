# CF conventions cheat sheet

A condensed reference for the parts of CF (Climate and Forecast) metadata
conventions that matter for plotting. Full spec: cfconventions.org.

## How skills use this file

`netcdf-inspect` consults this file when surfacing oddities to the user
(non-standard calendars, missing units, staggered grids). Plot skills
also rely on it for cell-methods interpretation (a "monthly precipitation"
file with `cell_methods="time: mean"` is a rate; with `time: sum` is an
accumulation — different conversion factors).

The `netcdf-reader.inspect()` MCP tool detects most of these conditions
automatically and reports them in `result.convention` and
`result.warnings`. This file is a human reference for context the MCP
cannot fully convey.

## Coordinate variables

A coordinate variable is a 1D variable with the same name as a dimension. It
defines the values of that axis. Look for these on every file:

- **Time**: usually `time`, sometimes `t`, `T`, `XTIME`. Has `units` like
  `"days since 1850-01-01"` and `calendar` attribute.
- **Longitude**: `lon`, `longitude`, `XLONG`. Units `degrees_east`.
- **Latitude**: `lat`, `latitude`, `XLAT`. Units `degrees_north`.
- **Vertical**: `lev`, `plev`, `pressure`, `z`, `depth`. Pressure usually
  in Pa or hPa; check units.

## Identifying coordinates without standard names

Check the `axis` or `standard_name` attribute:
- `axis="X"`, `standard_name="longitude"` — longitude
- `axis="Y"`, `standard_name="latitude"` — latitude
- `axis="Z"`, `positive="up"|"down"` — vertical
- `axis="T"`, `standard_name="time"` — time

WRF and other models sometimes have 2D coordinate variables (`XLONG(south_north,
west_east)`) instead of 1D. The `coordinates` attribute on the data variable
points to them.

## Calendars

The `calendar` attribute on a time variable can be:
- `gregorian` / `standard` — normal
- `proleptic_gregorian` — like gregorian but extended back before 1582
- `noleap` / `365_day` — every year is 365 days (common in CMIP)
- `360_day` — every month is 30 days (some climate models)
- `julian` — old Julian calendar

xarray decodes most of these via cftime when `decode_times=True` (the default
in modern xarray). Pandas datetime conversion fails on non-standard calendars.

## Cell methods

`cell_methods="time: mean"` says the variable is a time mean.
`cell_methods="time: mean (interval: 6 hours)"` is a 6-hourly mean.
`cell_methods="area: mean"` is an area average.

This affects interpretation: a "monthly precipitation" file with
`cell_methods="time: mean"` is an average rate; with `time: sum` it's an
accumulation. Don't mix them.

## Bounds variables

A coordinate may have a `bounds` attribute pointing to another variable that
gives cell edges. For accurate area calculations or pcolormesh plotting, use
the bounds rather than the cell centers.

## Missing values

`_FillValue` and `missing_value` mark missing data. xarray converts these to
NaN automatically when `decode_cf=True`.

## Units

CF requires SI-compatible units strings parsed by udunits. Examples:
- `"K"` — kelvin
- `"degC"` or `"degree_C"` — celsius
- `"kg m-2 s-1"` — precipitation flux
- `"m s-1"` — wind speed
- `"Pa"` — pressure

When converting for display:
- Temperature K → °C: `T - 273.15`
- Pressure Pa → hPa: `P / 100`
- Precip kg m⁻² s⁻¹ → mm/day: `× 86400`

## Attributes worth surfacing

When inspecting a file, these attributes (if present) tell the user a lot:
- `title`, `summary`, `source`, `institution` — global attrs
- `Conventions` — usually "CF-1.x"
- `frequency` (CMIP) — `mon`, `day`, `6hr`, etc.
- `experiment_id`, `source_id`, `variant_label` (CMIP6) — what model run
- `forecast_reference_time` — for forecasts

# Cycle 2 — `plot-renderer` MCP

> Design document for the second build cycle of `ncplot-agent`. Builds on
> cycle 1 (`netcdf-reader` MCP) — see
> `docs/specs/2026-05-06-cycle-1-netcdf-reader.md` for the upstream
> contract this design depends on.

**Status:** approved for implementation
**Date:** 2026-05-07
**Branch:** `cycle-2-plot-renderer`

---

## 1. Overview

A second MCP server, `plot-renderer`, that turns structured plot specs
into static figure files (PNG/PDF/SVG) for maps, time series, and
vertical profiles. Doesn't know about NetCDF, climate conventions, or
the agent — just rendering.

### Cycle 2 ships

- **3 callable tools:** `render_map`, `render_timeseries`, `render_profile`
- **Slim slice-file loader** — loose contract with cycle-1 NetCDF output
- **Render-oracle JSON sidecar** — tests assert on what was drawn, not pixels
- **Graceful degradation** when cartopy is missing — `render_map`
  ambiguity envelope; other tools keep working
- **`style_template` field** on all 3 render tools + a documented
  extraction-prompt template (`docs/style_template_extraction_prompt.md`)
  so any vision-capable agent can produce a valid template

### Cycle 2 explicitly does NOT ship

- Cross-section / Hovmöller (small follow-up cycle)
- Multi-panel composition (separate future tool)
- Animation / movie output
- Interactive viewers
- Land/ocean masking (cartopy can do it; opt-in field for a future cycle)
- Agent-side vision wiring for `style_template` extraction (cycle 3)

### Primary use cases

- WRF/ROMS B-tier files (10–100 GB) plotted from cycle-1 slice files
- CMIP and reanalysis (small enough for inline path)
- Both standalone-MCP usage and skill-driven (cycle 3) usage

### Non-goals

- Replacing matplotlib/cartopy
- Plotting any data the agent didn't already resolve through cycle-1
- Domain-specific scientific defaults (those live in cycle-3 skills)

---

## 2. Tool surface

Three callable tools. All return cycle-1's envelope shape:
`{ok: true, result, warnings}` on success,
`{ok: false, error: {code, message, context}}` on error,
`{ok: false, error: {code: "ambiguous", subcode, candidates, retry_with_param}}`
on ambiguity.

### 2.1 `render_map(spec) -> envelope`

**Input spec fields:**

```yaml
# Data — exactly one of these forms
values:        2D array (lat × lon)              # inline form
lon, lat:      1D coord arrays
# OR
slice_ref:     {path: ".../slice.nc", format: "netcdf", variable: "tos"}  # file form

# Presentation (optional; library defaults if absent)
projection:    "PlateCarree"|"Robinson"|"NorthPolarStereo"|...   # cartopy class name
extent:        [lon_min, lon_max, lat_min, lat_max]
lon_convention: "-180..180" | "0..360" | null     # if set, renderer shifts data
colormap:      string matplotlib name
vmin, vmax:    floats; OR clip_pct: [low, high]   # e.g. [2, 98]
vcenter:       float (forces diverging colormap centering)
title:         string
colorbar_label: string
colorbar_position: "right"|"bottom"|"top"|"left"|"none"
gridlines:     "none"|"light"|"heavy"
font_scale:    0.7-1.5
aspect:        float | "auto"

# Style-by-reference (overrides applied below explicit fields)
style_template: {colormap_kind, colormap_name, projection_family, ...}

# Output
output_path:   string (optional; auto-named if absent)
dpi:           int (default 150)
format:        "png"|"pdf"|"svg" (default "png")

# Behavior
downsample:    bool (default true; set false to disable Section 7's auto-downsample)
write_oracle_sidecar: bool (default false; tests/debug only)
```

**Response `result`:**

```yaml
output_path:    string
file_size_bytes: int
oracle:         {drawn fields — see §6}
plotted_min, plotted_max: float
plotted_shape:  [n_lat, n_lon]
applied_downsample: {factor, original_shape} | null
applied_lon_shift: bool
nan_fraction:   float
```

### 2.2 `render_timeseries(spec) -> envelope`

**Input spec fields:**

```yaml
# Data — multi-series
series:   [{values: 1D array, time: ISO strings, label: string, color?: string}, ...]
# OR sugar for single-series (mutually exclusive with `series`; supplying both
# returns error:invalid_spec with reason="series_and_sugar_both_set")
values, time, label?  →  normalized to series=[{...}]

# Presentation
title, ylabel, xlabel
aggregation:  "raw"|"monthly"|"annual"|"seasonal"   (applied per-series)
trendline:    null|"linear"|"lowess"
ymin, ymax
log_y:        bool
legend_placement: "best"|"outside_right"|"none"
font_scale, aspect

style_template, output_path, dpi, format, write_oracle_sidecar
```

**Response `result`:** `output_path`, `file_size_bytes`, `oracle`,
`series_count`, per-series
`[{label, n_points, plotted_min, plotted_max, nan_fraction, trendline_slope?}]`.

### 2.3 `render_profile(spec) -> envelope`

**Input spec fields:**

```yaml
# Data — multi-series (single-series sugar `values + vertical` also accepted;
# mutually exclusive with `series` per the same rule as render_timeseries)
series:   [{values: 1D array, vertical: 1D array, label: string, color?: string}, ...]
vertical_units:  "Pa"|"hPa"|"m"|"km"
vertical_axis:   "y"|"x"           (default "y")
invert_pressure: bool (default true if vertical_units in {Pa, hPa})
log_scale:       bool (default true if pressure)

# Presentation: title, xlabel, ylabel, legend_placement, font_scale, aspect
# Plus style_template, output_path, dpi, format, write_oracle_sidecar
```

**Response `result`:** `output_path`, `file_size_bytes`, `oracle`,
per-series stats.

### 2.4 Cross-tool conventions

- **Spec field precedence:** `explicit > style_template > library_default`.
  Style template never overrides an explicit user/skill choice.
- **Ambiguity envelopes** (renderer-emitted, all map to cycle-1's
  `{code: "ambiguous", subcode, candidates}` shape):
  - `cartopy_missing` — `render_map` only; candidate is install instruction
  - `unknown_colormap` — `colormap` string isn't in matplotlib's registry
  - `unknown_projection` — `render_map` only
  - `empty_slice` — array has zero cells (probably bad selection upstream)
  - `all_nan` — every cell is NaN
- **Errors** (non-recoverable): `output_path_invalid`,
  `output_dir_unwritable`, `slice_file_unreadable`,
  `internal_render_error`, `invalid_spec`,
  `format_extension_mismatch`, `unsupported_format`, `invalid_dpi`,
  `trendline_dependency_missing`.
- **Warnings** (success but flag): `auto_downsampled`, `constant_field`,
  `high_nan_fraction` (>50%), `lon_shift_applied`,
  `style_template_partially_applied`, `vcenter_outside_data_range`,
  `color_cycle_exceeded`.

---

## 3. Hand-off contract with cycle-1's `netcdf-reader`

The contract is **the on-disk slice file format and the inline-form
JSON shape** — not a Python import. Cycle 2 has its own NetCDF
dependency and does not import cycle 1; this is by design (loose
coupling between MCPs, §13.1.8).

### 3.1 Inline form — small slices, JSON over MCP

```json
{
  "form": "inline",
  "values":  [[[287.1, ...], ...]],
  "coords":  {"time": ["2024-09-01T12:00"], "lat": [...], "lon": [...]},
  "dims":    ["time", "lat", "lon"],
  "shape":   [1, 50, 60],
  "units":   "K",
  "long_name": "sea surface temperature"
}
```

NaN encoded as the JSON string `"NaN"`. Renderer adapter converts:
nested lists → `numpy.ndarray`, `"NaN"` → `np.nan`, ISO time strings →
`numpy.datetime64`. The renderer never sees JSON shape directly — the
adapter lifts to typed arrays before any rendering code runs.

### 3.2 File form — large slices, NetCDF on disk

```json
{
  "form": "file",
  "path":  ".ncplot/slices/<session>/<hash>.nc",
  "format": "netcdf",
  "variable": "tos",
  "size_bytes": 4640000,
  "dims":   ["time", "lat", "lon"]
}
```

Renderer adapter calls
`xarray.open_dataset(path, engine="h5netcdf", decode_times=True, chunks="auto")`
and selects `variable`. h5netcdf is a cycle-2 dep (matches cycle-1).

### 3.3 Required slice-file contents (frozen interface)

- Standard CF attributes on coordinates: `units`, `long_name`,
  `standard_name` where applicable
- Time encoded per CF (units like `"hours since 2000-01-01"` or already
  decoded with `cftime`)
- Latitude/longitude as 1D coords for rectilinear data, OR 2D coords
  for curvilinear (WRF/ROMS) — renderer handles both
- The named `variable` is present and accessible via `ds[variable]`
- No format-specific quirks beyond CF (cycle-1's normalization handles
  WRF/ROMS curvilinear etc. before writing the slice file)

If a slice file violates this contract (e.g., variable missing),
renderer returns `error: slice_file_unreadable` with the exception
type and the file path in `context`.

### 3.4 What we DON'T do

- Don't import cycle-1's Python package
- Don't validate the slice file against cycle-1's exact schema (any
  CF-compliant NetCDF works)
- Don't re-resolve selectors (cycle-1 already did that; the slice file
  IS the resolved data)

### 3.5 Skill-side ergonomics (cycle 3 preview)

```python
sl = read_slice(path, variable="tos", time="2024-09", region={...})
spec = {
  **sl["result"],          # forwards form + values/slice_ref + dims + units + ...
  "projection": "Robinson",
  "colormap": "RdYlBu_r",
  "title": "SST September 2024",
  "output_path": "sst_2024-09.png",
}
render_map(spec=spec)
```

The "spread the read_slice envelope, add presentation" pattern is the
documented integration shape.

---

## 4. Architecture

### 4.1 Per-render flow (same shape for all three tools)

1. **Spec validation** — required fields present, types correct.
   Errors → `error:invalid_spec`.
2. **Data normalization** — `adapter.normalize(spec)` returns either
   `(values, coords)` or raises a known exception type the tool maps
   to an envelope. Inline-form goes through `_from_inline()`;
   `slice_ref` goes through `slice_loader.load()`.
3. **Style application** — `style.apply(spec, style_template)` returns
   a *resolved* spec dict where every presentation field is filled by
   precedence: explicit > template > library default. Style happens
   BEFORE safety.
4. **Safety pass** — `safety.run(values, coords, spec)`:
   - Auto-downsample if cells > 4M and `downsample != False` →
     emit `warn("auto_downsampled", ...)`
   - Percentile clip if data spans > 6 orders of magnitude AND
     user/template didn't set vmin/vmax/clip_pct
   - NaN mask: rendered cells where values is NaN show as transparent
   - Lon shift if `lon_convention` set and data needs rolling
   - Empty slice → ambiguous envelope
   - All-NaN → ambiguous envelope
   - Constant field → continue but `warn("constant_field", ...)`
5. **Render** — tool-specific matplotlib/cartopy code. Returns `Figure`.
6. **Output** — `lifecycle.save(fig, spec)` resolves `output_path`
   (auto-name if missing), creates parent dirs, calls `fig.savefig(...)`,
   captures size.
7. **Oracle** — `oracle.capture(fig, spec, applied_safety)` builds the
   render-oracle JSON. In production: included as `result.oracle`.
   With `write_oracle_sidecar=True`: also written next to the figure.
8. **Envelope** — wrap result + accumulated warnings, return.

### 4.2 Why this layout

- **Per-tool files are thin.** Each `render_*.py` has only the
  matplotlib/cartopy drawing logic; everything reusable lives in
  shared modules.
- **Style/safety/oracle are tool-agnostic.** They work on a normalized
  data structure (working spec dict + numpy arrays), not on tool-specific
  shapes.
- **Cartopy is isolated.** Only `tools/render_map.py` imports cartopy.
  Module-level import in a `try/except`; the tool emits the
  `cartopy_missing` ambiguity envelope at call time. `render_timeseries`
  and `render_profile` keep working without cartopy installed.
- **Format-agnostic seam.** Same `⤴ format-agnostic — eligible for _core/ lift.`
  discipline as cycle 1, with `slice_loader.py` as the lone format-specific
  module.
- **Lifecycle separation.** Output dir lives in `.ncplot/figures/`;
  `lifecycle.py` owns auto-naming, parent-dir creation, and the
  `gitignore` line.

### 4.3 Library defaults (`defaults.py`)

```python
LIBRARY_DEFAULTS = {
    "colormap":          "viridis",
    "projection":        "PlateCarree",
    "colorbar_position": "right",
    "gridlines":         "light",
    "font_scale":        1.0,
    "aspect":            "auto",
    "dpi":               150,
    "format":            "png",
    "downsample":        True,
    "log_scale":         False,    # render_profile overrides to True if pressure
}
```

No "anomaly → RdBu_r" logic here. That's cycle-3 skill work, supplied
via explicit `colormap=...` in the spec.

### 4.4 Style application precedence

```
final_spec[field] = explicit_spec.get(field)
                 or style_template_mapped.get(field)
                 or LIBRARY_DEFAULTS[field]
```

`style_template_mapped` is the result of running the style-template
through the mapping table (§8.2).

---

## 5. Output management & lifecycle

### 5.1 Output directory

- Default: `.ncplot/figures/` at the project root (CWD when the MCP
  server is invoked).
- Created lazily on first write.
- No session subdirectory — figures persist across sessions.
- `.gitignore` updated in cycle 2 to add `.ncplot/figures/`.
- The figures dir is **never** auto-cleaned. User owns the contents.

### 5.2 Output path resolution

1. **`output_path` provided in spec.**
   - Absolute path → used as-is.
   - Relative path → resolved against CWD (not against `.ncplot/figures/`).
   - Parent dir created if missing.
   - Filename extension determines format unless `format` is also
     explicit (then they must agree, else `error:format_extension_mismatch`).
   - File overwrite is silent (caller asked for that path).
2. **`output_path` absent.**
   - Auto-name: `.ncplot/figures/{tool}_{var_or_label}_{when}_{hash6}.{format}`
     - `tool` ∈ `map`, `timeseries`, `profile`
     - `var_or_label` is `spec["variable"]`, falling back to
       `spec["title"]`'s slug, falling back to `"plot"`
     - `when` is the first time-coord value as `YYYY-MM-DD`
       (or `YYYY-MM` if monthly), or `multi` for multi-series, or
       `unknown` if no time
     - `hash6` is the first 6 chars of `sha256(canonical_json(spec))` —
       disambiguates re-renders with different presentation
   - Examples:
     - `.ncplot/figures/map_tos_2024-09_a3f72b.png`
     - `.ncplot/figures/timeseries_tas_multi_5e1c08.png`
     - `.ncplot/figures/profile_temperature_unknown_d04ea1.svg`

### 5.3 Format & DPI

- Supported formats: `png` (default), `pdf`, `svg`. Rejected formats →
  `error:unsupported_format` listing the supported set.
- `dpi` default 150. Range 72–600. Out-of-range → `error:invalid_dpi`.
- For `pdf`/`svg`, `dpi` only affects raster components (e.g.,
  rasterized `pcolormesh`); vector elements stay vector.

### 5.4 Atomic write

- Renderer writes to `<output_path>.tmp` and `os.replace()` to the
  final name. POSIX atomic; best-effort on Windows.
- On failure during render or save, the `.tmp` is removed in a
  `finally:` block; partial files don't leak.

### 5.5 Render-oracle sidecar

- In production: oracle is in `result.oracle` and not written to disk.
- Tests / debug: `spec["write_oracle_sidecar"] = True` writes
  `<output_path>.oracle.json` next to the figure. Off by default.

### 5.6 Lifecycle hooks

- **No startup cleanup** — figures persist.
- **No shutdown cleanup** — figures persist.
- **Single startup check:** ensure `.ncplot/` exists if any figure has
  ever been written there (otherwise lazy creation handles it).
  Effectively no-op.

### 5.7 Disk-usage caveats

- We do *not* cap the figures dir size.
- We do not deduplicate (the `hash6` suffix means identical specs
  hash to the same name and overwrite, but two specs differing only
  by a label produce two files).
- A future cycle could add `--prune-figures-older-than` CLI; out of
  scope here.

---

## 6. Render-oracle JSON

### 6.1 Purpose

The oracle is the renderer's *observable behavior in machine-readable
form*. Tests assert against this JSON instead of pixels. Also lands
in the response envelope (`result.oracle`) so the agent or a CLI can
answer "what did the renderer actually do?" without re-opening the PNG.

### 6.2 Schema (common to all 3 tools)

```yaml
oracle_schema_version: 1
tool: "render_map" | "render_timeseries" | "render_profile"
output:
  path:        string
  format:      "png"|"pdf"|"svg"
  size_bytes:  int
  dpi:         int
  width_px:    int
  height_px:   int

data:
  shape:                 [int, ...]
  plotted_min:           float | null    # null if all-NaN
  plotted_max:           float | null
  nan_fraction:          float
  applied_downsample:    {factor: int, original_shape: [...]} | null
  applied_lon_shift:     bool | null     # render_map only; null otherwise
  applied_clip_pct:      [float, float] | null
  vmin_used:             float
  vmax_used:             float

style_resolution:
  # For every presentation field, the source it came from.
  # source ∈ "explicit" | "style_template" | "library_default"
  colormap:           {value: string,  source: string}
  projection:         {value: string,  source: string}    # render_map only
  colorbar_position:  {value: string,  source: string}
  gridlines:          {value: string,  source: string}
  font_scale:         {value: float,   source: string}
  aspect:             {value: float|"auto", source: string}
  # … one entry per resolved presentation field

drawn:
  title:               string | null
  colorbar_label:      string | null
  axis_labels:         {x: string|null, y: string|null}
  legend_present:      bool
  legend_entries:      [string, ...] | null
  gridlines_drawn:     bool
  coastlines_drawn:    bool             # render_map only
  # render_map:
  projection_class:    string | null
  extent:              [w, e, s, n] | null
  # render_timeseries / render_profile:
  series_count:        int
  series:              [{label, n_points, line_color, line_style}, ...]
  trendline_present:   bool             # render_timeseries only
  trendline_kind:      "linear"|"lowess"|null
  vertical_axis:       "x"|"y"          # render_profile only
  log_scale:           bool             # render_profile only
  invert_pressure:     bool             # render_profile only

style_template_applied:
  # null if no style_template was supplied.
  fields_applied:    [string, ...]    # spec field names taken from template
  fields_ignored:    [{field: string, reason: string}, ...]
  source:            {image_path, extracted_by, extracted_at, confidence} | null
```

### 6.3 Population

`oracle.py` exposes one function:

```python
def capture(
    fig: matplotlib.figure.Figure,
    spec: dict,
    resolved_spec: dict,        # post-style-application working spec
    safety_actions: dict,       # what safety pass did
    style_template_trace: dict, # which template fields applied
) -> dict:
    ...
```

Reads from `fig.axes[...]` (titles, labels, colorbar, lines, etc.)
and from the resolved spec — so the oracle reflects *what was actually
drawn*, not just *what was requested*. Each per-tool render module
registers a hook adding tool-specific drawn fields after `Figure` is
built.

### 6.4 Why this is sufficient for tests

- Catches the regressions image-diff catches: wrong colormap
  (`drawn.colormap`), wrong vmin (`data.vmin_used`), missing title
  (`drawn.title is None`), broken lon shift
  (`data.applied_lon_shift is False` when test expected True).
- Doesn't depend on pixel rendering, font availability, or cartopy
  version.
- Single place for tests to read everything.
- Doubles as a debugging tool.

### 6.5 Test patterns

1. **Per-tool unit tests** — assert oracle fields without writing PNGs
   to disk where possible.
2. **End-to-end smoke** — render to disk, assert PNG exists & size
   > 5 KB, plus oracle assertions.
3. **Style-template tests** — supply known template, assert
   `style_template_applied.fields_applied` matches and
   `style_resolution.<field>.source == "style_template"`.

### 6.6 Pixel-diff escape hatch

A `pytest --image-diff` flag (default off) runs a separate suite that
compares against committed golden PNGs in `tests/golden/` with SSIM
tolerance ≥0.95. Used during release reviews; not on every CI run.
Re-bless via `pytest --image-diff --regenerate-golden`.

---

## 7. Robustness behaviors

This section consolidates safety-pass owned behaviors.

### 7.1 Large arrays

- **Threshold:** total cells > 4,000,000 (i.e., > 2048 × 2048 for
  square map).
- **Default:** auto-downsample via
  `xarray.DataArray.coarsen(factor=k, boundary="trim").mean()`,
  computed independently per spatial axis.
- **1D arrays** (`render_timeseries`): threshold > 100,000 points;
  uses stride decimation `arr[::k]` (LTTB-style is a future improvement).
- **`render_profile` vertical:** no downsample (vertical levels
  usually < 200).
- **Override:** `spec["downsample"] = False` disables the auto-downsample;
  no warning emitted in that case.
- **Warning on auto-downsample:**
  ```json
  {"code": "auto_downsampled", "tool": "render_map",
   "from_shape": [4000, 4000], "to_shape": [2000, 2000],
   "factor": {"lat": 2, "lon": 2}}
  ```
- **Renderer fast paths:** maps use `pcolormesh` with `rasterized=True`.

### 7.2 NaN handling

- Cells with NaN render as transparent
  (`matplotlib.colormap.set_bad(alpha=0)`).
- `nan_fraction` reported in oracle and result.
- If `nan_fraction > 0.5`, emit warning `high_nan_fraction`.
- If `nan_fraction == 1.0`, return ambiguity envelope
  `code: "ambiguous", subcode: "all_nan"`. Candidate retry param: a
  non-empty `region` or `time` selector upstream.

### 7.3 Longitude convention (`render_map` only)

- If `spec["lon_convention"]` is set AND data's lon coords don't match
  (e.g., spec says `"-180..180"` but data is `0..360`), apply
  `xarray.Dataset.roll(lon=shift)` and adjust coord to requested
  convention.
- `oracle.data.applied_lon_shift = True` and `lon_shift_applied`
  warning emitted.
- If `lon_convention` not provided, no shift; lon plotted as given.
- The shift never changes data values, only array layout.

### 7.4 Constant field

- If `plotted_min == plotted_max`, still render but emit
  `constant_field` warning with the constant value in `context`.

### 7.5 Cartopy degradation

```python
# tools/render_map.py
try:
    import cartopy.crs as ccrs
    import cartopy.feature as cfeature
    _CARTOPY_OK = True
    _CARTOPY_IMPORT_ERROR = None
except ImportError as e:
    _CARTOPY_OK = False
    _CARTOPY_IMPORT_ERROR = str(e)


def render_map(spec):
    if not _CARTOPY_OK:
        return envelope.ambiguous(
            subcode="cartopy_missing",
            message=("cartopy is not installed. Install with "
                     "`uv pip install cartopy` or wait for cycle-5 auto-install."),
            candidates=[
                {"param": "install", "value": "uv pip install cartopy",
                 "kind": "shell_command"},
                {"param": "install", "value": "conda install -c conda-forge cartopy",
                 "kind": "shell_command"},
            ],
            retry_with_param=None,
            context={"import_error": _CARTOPY_IMPORT_ERROR},
        )
    # ... rest of render_map
```

`render_timeseries` and `render_profile` do not depend on cartopy.

### 7.6 What's not in cycle 2

- **No memory cap.** If user passes a 100 GB inline array, Python OOMs.
  Slice files exist precisely to keep agent and renderer memory bounded.
- **No render timeout.** Slow renders take time. A future MCP-level
  timeout might wrap calls.
- **No retry on save failure.** `.tmp` is cleaned and `error` envelope
  returned. Caller decides on retry.

---

## 8. Style-template: schema, mapping, application

The renderer accepts a `style_template` field on every render call.
Cycle 2 ships:

1. The JSON schema below (locked as the cross-MCP / cross-cycle contract).
2. The deterministic application logic in `style.py`.
3. A documented vision-extraction prompt template at
   `docs/style_template_extraction_prompt.md` so any vision-capable
   agent (cycle 3 onward) can produce a valid template from a reference
   image.

### 8.1 Schema

```yaml
# All fields optional. Unknown fields are recorded and ignored (forward-compat).
style_template:
  # Color treatment
  colormap_kind:    "sequential"|"diverging"|"categorical"|null
  colormap_name:    string|null    # explicit matplotlib name; takes precedence over kind
  vcenter:          float|null     # for diverging
  clip_pct:         [low, high]|null

  # Map-only
  projection_family: "plate_carree"|"robinson"
                  |  "polar_stereo_north"|"polar_stereo_south"
                  |  "lambert_conformal"|"mercator"|null
  extent_hint:      "global"|"hemispheric"|"regional"|null

  # Layout
  colorbar_position: "right"|"bottom"|"top"|"left"|"none"|null
  legend_placement:  "best"|"outside_right"|"outside_bottom"|"none"|null
  gridlines:         "none"|"light"|"heavy"|null
  aspect:            float|"auto"|null
  font_scale:        float (0.7-1.5)|null

  # Annotation density
  title_placement:   "top"|"none"|null
  label_density:     "minimal"|"normal"|"verbose"|null

  # Provenance (optional but recommended)
  source:
    image_path:     string|null
    extracted_by:   string|null    # e.g. "claude-opus-4-7" or "manual"
    extracted_at:   ISO timestamp|null
    confidence:     float 0.0-1.0|null
```

### 8.2 Mapping table — `style_template` → spec field

`style.py` owns the deterministic mapping. Resolution order at every
field is `explicit > template > library_default`.

| `style_template` field        | maps to spec field | mapping logic |
|-------------------------------|--------------------|---------------|
| `colormap_name`               | `colormap`         | direct |
| `colormap_kind = "sequential"` | `colormap`         | → `"viridis"` if no `colormap_name` |
| `colormap_kind = "diverging"`  | `colormap` + `vcenter` | → `"RdBu_r"`, `vcenter = 0.0` if no explicit |
| `colormap_kind = "categorical"` | `colormap`        | → `"tab10"` |
| `clip_pct`                    | `clip_pct`         | direct |
| `vcenter`                     | `vcenter`          | direct |
| `projection_family = "plate_carree"` | `projection` | → `"PlateCarree"` |
| `projection_family = "robinson"`     | `projection` | → `"Robinson"` |
| `projection_family = "polar_stereo_north"` | `projection` | → `"NorthPolarStereo"` |
| `projection_family = "polar_stereo_south"` | `projection` | → `"SouthPolarStereo"` |
| `projection_family = "lambert_conformal"`  | `projection` | → `"LambertConformal"` |
| `projection_family = "mercator"`           | `projection` | → `"Mercator"` |
| `extent_hint`                 | (advisory only)    | influences default extent if no explicit `extent` (e.g. `"hemispheric"` + N-pole projection sets extent appropriately); never overrides explicit |
| `colorbar_position`           | `colorbar_position` | direct |
| `legend_placement`            | `legend_placement` | direct |
| `gridlines`                   | `gridlines`        | direct |
| `aspect`                      | `aspect`           | direct |
| `font_scale`                  | `font_scale`       | clamped to [0.7, 1.5] |
| `title_placement`             | (advisory)         | controls whether `title` is rendered if user supplied one |
| `label_density`               | (advisory)         | controls auto-tick density and grid label visibility |

### 8.3 Application algorithm

```python
def apply(spec: dict, template: dict | None) -> tuple[dict, dict]:
    """Return (resolved_spec, trace).
    trace = {fields_applied: [...], fields_ignored: [...]}.
    """
    resolved = dict(spec)
    trace = {"fields_applied": [], "fields_ignored": []}

    if template is None:
        return resolved, trace

    for tmpl_field, value in template.items():
        if value is None:
            continue
        spec_field, mapped_value, ok, reason = _MAPPING.get(tmpl_field)(value)
        if not ok:
            trace["fields_ignored"].append({"field": tmpl_field, "reason": reason})
            continue
        if spec_field in resolved and resolved[spec_field] is not None:
            trace["fields_ignored"].append(
                {"field": tmpl_field, "reason": "overridden_by_explicit_spec"})
            continue
        resolved[spec_field] = mapped_value
        trace["fields_applied"].append(tmpl_field)
    return resolved, trace
```

The trace lands in `oracle.style_template_applied`.

### 8.4 Validation & errors

- Unknown `colormap_kind` → ignored, `fields_ignored` with
  `reason="unknown_colormap_kind"`. Not a hard error.
- `projection_family` not in table → ignored similarly.
- `font_scale` out of range → clamped, recorded as `fields_applied`
  with note in oracle.
- A completely empty `style_template = {}` is valid (no-op).
- A `style_template` field present but `null` is valid (no-op).

### 8.5 Provenance pass-through

The `source` block flows through the renderer untouched and lands in
`oracle.style_template_applied.source`. Useful for cycle-3
skill-refiner to track which plots came from which reference images.

### 8.6 Out of scope (locked, not deferred)

- **Renderer never invokes vision** — purely deterministic application
  of a JSON template.
- **Image hashing or perceptual matching** — not a feature.
- **Style transfer for non-supported plot types** — cross-section/
  Hovmöller (deferred cycles) extend the table when added.

### 8.7 The extraction-prompt doc

`docs/style_template_extraction_prompt.md` (new in cycle 2) contains:
- The full schema with field-by-field guidance for what a vision LLM
  should look at.
- A few-shot example: an image + its expected JSON.
- Confidence-scoring guidance.

This doc is the contract cycle-3 skills will use when wiring up the
vision step.

---

## 9. Format-agnostic seam discipline

### 9.1 Two seams in cycle 2

**Seam A — input format (NetCDF vs future Zarr/GRIB/HDF5).**

- Format-specific in cycle 2: `slice_loader.py` only.
- Everything else (`adapter.py`, `style.py`, `defaults.py`, `safety.py`,
  `oracle.py`, `lifecycle.py`) is format-agnostic and carries the
  `⤴ format-agnostic — eligible for _core/ lift.` marker.
- Per-tool render modules consume normalized numpy arrays and a
  resolved spec dict; never look at the slice file.

**Seam B — plot library (matplotlib + cartopy vs alternatives).**

- We do **not** abstract this in cycle 2. Matplotlib is the assumed
  backend; rewriting for plotly is a fresh MCP, not a swap inside
  this one.
- The tool *contract* (input spec, response envelope, oracle schema)
  is library-neutral, so a future plotly-renderer MCP could be a
  sibling of plot-renderer with the same external surface.

### 9.2 The seam test

`tests/mcp/plot_renderer/unit/test_seam.py` enforces format-agnostic
discipline by AST-walking every non-format-specific module and
asserting it does NOT import:

- `netCDF4`, `h5netcdf`, `cftime`, `pynio`, `cfgrib`, `zarr` (input formats)
- The cycle-1 package directly (loose coupling, §13.1.8)

`slice_loader.py` is the only file allowed those imports; the test
reads its module-level `__format_specific__ = True` marker and skips it.

A separate but lighter assertion: only `tools/render_map.py` may
import cartopy.

### 9.3 How a future Zarr-renderer slots in

```python
# slice_loader.py  ← grow here
def load(slice_ref: dict) -> xarray.DataArray:
    fmt = slice_ref["format"]
    if fmt == "netcdf":
        return _load_netcdf(slice_ref)
    elif fmt == "zarr":
        return _load_zarr(slice_ref)        # NEW
    raise UnsupportedFormatError(fmt)
```

No other file changes.

### 9.4 Optional `_core/` lift

Same posture as cycle 1: don't lift yet. Trigger: when a third reader
(say, GRIB) ships, lift the shared format-agnostic modules from
cycle-1 and cycle-2 into a sibling package.

---

## 10. Module layout

### 10.1 Source files

```
src/mcp/plot_renderer/
├── __init__.py                          (~5 LOC)
├── pyproject.toml                       package metadata
├── README.md                            (already exists; will be updated)
├── server.py                            ~150 LOC; MCP wiring + dispatch
├── envelope.py                          ~80 LOC; copy of cycle-1's envelope.py (locked schema)
├── protocols.py                         ~50 LOC; FormatAdapter-style Protocol for slice_loader (⤴)
├── adapter.py                           ~120 LOC; spec → typed numpy arrays + DataArray (⤴)
├── slice_loader.py                      ~80 LOC; NetCDF-only loader (FORMAT-SPECIFIC; __format_specific__ = True)
├── style.py                             ~150 LOC; style_template application + mapping table (⤴)
├── defaults.py                          ~30 LOC; LIBRARY_DEFAULTS dict (⤴)
├── safety.py                            ~180 LOC; downsample, NaN, clip, lon-shift, constant-field, all-NaN (⤴)
├── oracle.py                            ~200 LOC; oracle JSON capture from Figure (⤴)
├── lifecycle.py                         ~100 LOC; output dir, auto-name, atomic save (⤴)
├── colormap_registry.py                 ~40 LOC; matplotlib cmap validation + safe lookup (⤴)
└── tools/
    ├── __init__.py
    ├── render_map.py                    ~250 LOC; cartopy import guard + map drawing (cartopy-specific)
    ├── render_timeseries.py             ~180 LOC; line plotting, multi-series, trendlines (⤴)
    └── render_profile.py                ~180 LOC; vertical profile, log scale, pressure invert (⤴)
```

### 10.2 Test files

```
tests/mcp/plot_renderer/
├── conftest.py                          fixtures: small fake DataArrays, fake slice files, fake matplotlib backend
├── unit/
│   ├── test_envelope.py
│   ├── test_adapter_inline.py           inline-form normalization
│   ├── test_adapter_slice_ref.py        slice_ref form
│   ├── test_slice_loader.py             NetCDF loader unit tests
│   ├── test_style_application.py        every mapping-table row + precedence
│   ├── test_safety_downsample.py        threshold logic, override
│   ├── test_safety_nan.py               NaN mask, all-NaN ambiguity
│   ├── test_safety_lon_shift.py         0..360 ↔ -180..180
│   ├── test_safety_constant.py
│   ├── test_oracle_schema.py            schema completeness for each tool
│   ├── test_lifecycle_output_path.py    explicit, auto-name, parent-dir create, atomic write
│   ├── test_colormap_registry.py
│   ├── test_render_map.py               with cartopy
│   ├── test_render_map_no_cartopy.py    monkeypatched ImportError → ambiguity envelope
│   ├── test_render_timeseries.py        single + multi-series, trendline
│   ├── test_render_profile.py           pressure-invert, log scale, multi-series
│   ├── test_style_template_full.py      all template fields applied
│   ├── test_style_template_partial.py   partial template; trace correctness
│   ├── test_style_template_unknown.py   unknown fields → fields_ignored
│   └── test_seam.py                     format-agnostic discipline + cartopy isolation
└── integration/
    ├── test_pipeline_inline.py          inline-form e2e: spec → PNG + oracle
    ├── test_pipeline_slice_ref.py       file-form e2e: cycle-1 slice → render
    ├── test_three_tools_smoke.py        each tool produces a non-empty PNG
    └── test_image_diff_optional.py      gated on --image-diff flag; SSIM vs golden/

tests/golden/                            committed reference PNGs for image-diff (small set)
docs/
├── specs/2026-05-07-cycle-2-plot-renderer.md          THIS spec
├── plans/2026-05-07-cycle-2-plot-renderer.md          (writing-plans output)
└── style_template_extraction_prompt.md                cycle-2 deliverable
```

### 10.3 Naming notes

- Disk path `src/mcp/plot_renderer/` (underscore for Python import);
  MCP server external name `plot-renderer` (hyphen). Same convention
  as cycle 1.
- `protocols.py` houses the slice-loader Protocol — same pattern
  cycle 1 needed for the FormatAdapter seam test.
- `colormap_registry.py` is split out so `style.py` can validate cmap
  names without importing matplotlib at module load (lazy validation;
  matplotlib loads on first call only).

### 10.4 Cycle-2 dependency declaration

Inner `pyproject.toml`:

```toml
[project]
name = "plot-renderer"
dependencies = [
    "mcp>=1.0",
    "matplotlib>=3.8",
    "numpy>=1.24",
    "xarray>=2024.1",
    "h5netcdf>=1.3",
    "dask[array]>=2024.1",
]

[project.optional-dependencies]
maps     = ["cartopy>=0.22"]
trend    = ["scipy>=1.11"]
dev      = ["pytest>=8", "ruff>=0.5", "mypy>=1.10", "scikit-image>=0.22"]
```

Notes:
- **Cartopy is opt-in.** Cycle 5's auto-installer activates it; without
  it, `render_map` returns the ambiguity envelope.
- **scipy is opt-in.** `trendline="lowess"` requires it; if absent that
  path returns `error: trendline_dependency_missing`. `trendline="linear"`
  uses pure numpy and always works.
- **No netcdf4-python.** h5netcdf is sufficient and matches cycle-1.

---

## 11. Testing strategy

### 11.1 Layer 1 — unit tests (~22 files)

Per-module tests with no disk I/O where avoidable.
`matplotlib.use("Agg")` set globally in `conftest.py`.

- **Adapter:** inline-form normalization, NaN encoding round-trip,
  slice_ref loader.
- **Style:** every mapping row, precedence, unknown-field, partial
  templates, trace correctness.
- **Safety:** downsample threshold + override, NaN mask + all-NaN
  ambiguity, lon-shift, constant-field, percentile clip.
- **Oracle:** schema completeness for each tool.
- **Lifecycle:** explicit/auto-name resolution, parent-dir creation,
  atomic write, format-extension agreement.
- **Per-tool render:** drawing logic with mocked Figure assertions
  where possible, real Figure for output checks.
- **Cartopy degradation:** `test_render_map_no_cartopy.py` patches
  `_CARTOPY_OK = False`, asserts the ambiguity envelope.
- **Seam test:** AST-walk every `⤴` module asserting no format-specific
  imports + only `tools/render_map.py` imports cartopy.

### 11.2 Layer 2 — integration tests (~4 files)

End-to-end with real files written to `tmp_path`:

- **Inline form:** synthetic `xarray.Dataset` → spec → render_map →
  PNG > 5 KB + oracle assertions.
- **Slice-ref form:** write small NetCDF (cycle-1 fixture pattern) →
  spec with `slice_ref` → render → asserts.
- **Three-tools smoke:** drive each tool once with minimal valid spec.
- **Style-template e2e:** known template → render → verify via oracle.

### 11.3 Layer 3 — image-diff (opt-in, gated)

Gated on `pytest --image-diff`. Compares ~6 reference plots against
`tests/golden/` PNGs using SSIM ≥0.95.

Golden set: a CF map (Robinson), a polar map (NorthPolarStereo), a
2-series time series with linear trendline, a profile in pressure
with log-y, a style-template-applied map, and a small WRF-curvilinear
map (catches 2D-coord drawing path).

Re-bless: `pytest --image-diff --regenerate-golden`.

### 11.4 Layer 4 — pinned-files integration (opt-in, real data)

Same pattern as cycle-1's `test_real_files.py`:

- Skipped unless `NCPLOT_REAL_FILES=1`.
- Reads paths from `tests/integration/real_files.json` (gitignored).
- Drives each render tool against actual WRF/ROMS/CMIP files through
  cycle-1's read_slice → cycle-2's render_*. Asserts no exceptions,
  PNG > 50 KB, `nan_fraction < 1.0`.
- Documented setup: `docs/REAL_FILES_SETUP.md`.

### 11.5 What we don't test in cycle 2

- **Pixel-perfect diffs.** Replaced by oracle + SSIM.
- **Cross-platform font rendering.** Oracle asserts requested title
  text, not glyph metrics.
- **Performance benchmarks.** Future cycle.
- **MCP transport-level integration.** Cycle-1 made the same call.

### 11.6 CI shape

`pytest tests/mcp/plot_renderer/unit tests/mcp/plot_renderer/integration`
default. Image-diff and real-files are opt-in flags. Cycle 2 doesn't
change top-level `pyproject.toml`, only adds new test files.

---

## 12. Open risks

### 12.1 Cartopy install fragility

**Trigger:** PROJ/GEOS C deps; `pip install cartopy` fails on fresh
systems.
**Response:** Graceful degradation in §7.5 — `render_map` returns the
`cartopy_missing` ambiguity envelope; other tools keep working. Cycle 5
closes this with the auto-installer.

### 12.2 Oracle schema drift

**Trigger:** Renamed/dropped oracle fields rot tests silently.
**Response:** `_REQUIRED_ORACLE_FIELDS` list asserted at oracle-build
time. `test_oracle_schema.py` keeps the contract pinned.
`oracle_schema_version` ticks per cycle for additions.

### 12.3 Style-template confidence vs determinism

**Trigger:** Vision-LLM extracts `colormap_kind="diverging"` for
all-positive data.
**Response:** Renderer is deterministic by design; oracle records
`fields_applied`. Cycle-2 ships ONE sanity warning:
`vcenter_outside_data_range` if `vcenter` set but data range doesn't
straddle zero.

### 12.4 Multi-series color collisions

**Trigger:** > 10 series; default cycle repeats.
**Response:** Use `tab10` cycle by default; emit
`color_cycle_exceeded` when `len(series) > 10` and switch to `tab20`.
> 20: pointed warning that caller should pass colors explicitly.

### 12.5 Atomic-write race on Windows

**Trigger:** `os.replace()` can `PermissionError` on Windows when
another process holds the file open.
**Response:** Documented POSIX assumption. Windows fallback:
`os.remove()` + `os.rename()` with one retry. Test on Linux only.

### 12.6 Slice-file convention drift

**Trigger:** Cycle-1 future change writes non-CF metadata.
**Response:** Slice-file contract (§3) is locked in this spec; cycle-1
changes touching the format must update this contract.
`test_pipeline_slice_ref.py` is the regression test.

### 12.7 Lowess trendline scipy dependency

**Trigger:** `trendline="lowess"` without scipy installed.
**Response:** Already in design (§10).
`error: trendline_dependency_missing`. No fallback to linear.

### 12.8 Memory pressure on inline-form decoding

**Trigger:** 5 GB inline-form `values`.
**Response:** Out of scope. Cycle-1's `max_inline_bytes=100_000`
prevents the realistic path.

### 12.9 Style-template forward-compat

**Trigger:** Future cycle adds new template field.
**Response:** `style.apply()` records unknown fields in
`fields_ignored` with `reason="unknown_template_field"`.

### 12.10 The "looks fine but is wrong" risk

**Trigger:** User trusts a plot the renderer produced with hidden
clip / shift / downsample.
**Response:** All safety actions surface in warnings + oracle.
Cycle-3 skills will be required to surface warnings to the user.

---

## 13. Cross-cutting principles

### 13.1 Inherited from cycle 1

1. **Envelope discipline.** No raw exceptions cross the MCP boundary.
2. **Format-agnostic seam.** Files marked `⤴` may not import
   format-specific libraries. Enforced by `test_seam.py`.
3. **TDD per task.** Failing-test → minimal-implementation → green →
   commit.
4. **Atomic commits.** Each plan step ends with a commit.
5. **No silent fallback.** Clear envelope on missing dep / bad input.
6. **Selectors / specs are canonical.** Renderer takes a fully-resolved
   spec.
7. **Caching only where it pays.** Cycle 2 caches nothing internally.
8. **Loose coupling between MCPs.** Contracts are JSON shapes and
   on-disk formats — not Python imports.
9. **MCP server external name uses hyphens (`plot-renderer`); on-disk
   Python package uses underscores (`plot_renderer`).**

### 13.2 New for cycle 2

10. **Renderer is library-default-safe.** Domain knowledge lives in
    skills, not the renderer.
11. **Observability over inference.** Every safety action recorded in
    oracle and envelope. Tests assert observable behavior, not pixels.
12. **One cartopy-aware module.** Only `tools/render_map.py` imports
    cartopy.
13. **Style-template is deterministic.** No vision, no inference inside
    the renderer.
14. **Explicit beats template beats default.** Triple-precedence rule
    codified in `style.py`.
15. **Plot files are user-owned artifacts.** `.ncplot/figures/` never
    auto-cleaned.
16. **Output writes are atomic on POSIX.** Best-effort on Windows.
17. **Oracle is the test contract.** Versioned via
    `oracle_schema_version`; additions append-only within a version.
18. **Forward-compat by ignoring unknown fields.** Unknown
    style-template / spec fields recorded in oracle, not errored.

### 13.3 What cycle 2 explicitly does not establish

- **Plot-library abstraction.** Replaceability lives at the MCP
  boundary, not inside the package.
- **A `_core/` shared package.** Same posture as cycle 1.
- **A panel/grid composition tool.** Single-figure tools only.
- **Vision in the renderer.** Style extraction is the agent's job.

---

## End of spec

Implementation plan (writing-plans output) goes in
`docs/plans/2026-05-07-cycle-2-plot-renderer.md`.

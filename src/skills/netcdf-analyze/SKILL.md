---
name: netcdf-analyze
description: Run array-shaped analysis on a NetCDF file — index-mode hyperslab with stride, dimension reduction via {avg/min/max/sum/rms/total}, and CDL text dump. Use whenever the request is about extracting / reducing / inspecting the raw array (not about producing a plot). Mirrors NCO's ncks (-d) and ncwa (-y) and ncks (--cdl), with output that is bit-exact identical to those tools (within ULP for accumulating ops). Always run netcdf-inspect first if the file hasn't been inspected this session.
---

# netcdf-analyze

## When to use

The request is about the **array**, not a **plot**:

- "Pull every other timestep of T between indices 100 and 200"
- "Average SST over lat and lon to get a global mean per month"
- "Dump the CDL of `foo.nc` so I can grep its structure"
- "Reduce this variable to a scalar by averaging all dims"

If the user says "plot", "render", "show me a chart", route to
`netcdf-plot-{router,map,timeseries,profile}` instead.

## Three tools, one mental model

All three are MCP tools on the `netcdf-reader` server.

| Tool | NCO analog | What it does |
|---|---|---|
| `read_slice(..., index_selectors={dim: [start, stop, stride?]})` | `ncks -d dim,start,stop,stride` | Index-mode hyperslab. Stop is **inclusive** (ncks convention). Stride defaults to 1. Combine multiple dims in one call. |
| `reduce_variable(path, variable, reduce_dims, op)` | `ncwa -y <op> -a <dims>` | Collapse a variable along named dims. `op` ∈ {avg, min, max, sum, rms, total}. `total` is an ncks-ism for `sum`. `reduce_dims=[]` → reduce all dims → scalar. |
| `dump_cdl(path, *, variables=None, header_only=False)` | `ncks --cdl` (or `ncks --cdl -m` for header-only) | Emit CDL text. `variables=[...]` restricts subset; `header_only=True` omits the data: section. |

## Quick reference

1. **Confirm inspection.** If `netcdf-inspect` hasn't run on this
   file/glob, run it now so you know the dim names, dtypes, and
   value ranges.
2. **Resolve variable name** via `find_variables` if the user
   named it informally.
3. **Pick the tool** by intent:
   - Subsetting an array → `read_slice` (with the existing
     `time=`/`lat=`/`lon=` selectors and/or the new
     `index_selectors=`).
   - Reducing dims → `reduce_variable`.
   - Schema-only or structure dump → `dump_cdl`.
4. **Mind the dim semantics:**
   - `index_selectors` is **index-space, stop-inclusive, stride-aware**.
     `[0, 5]` gives 6 values (0..5).
     `[0, 11, 2]` gives 6 values (0,2,4,6,8,10).
   - `reduce_dims` accepts dim names case-insensitively. `[]`
     means "all dims → scalar".
   - `index_selectors` is **mutually exclusive on the same dim**
     with the named selectors (`time=`, `lat=`, etc.). Different
     dims is fine.
5. **Surface the units, shape, op, and reduced_dims** from the
   envelope when reporting back to the user.

## Worked example — global time-mean

User: "What's the time-mean SST per (lat, lon) for the whole record?"

```text
1) inspect("sst.nc")
   → variable "sst" lives on (time=120, lat=180, lon=360)
2) reduce_variable(
     "sst.nc", variable="sst",
     reduce_dims=["time"], op="avg")
   → result.values: shape (180, 360)
     result.dims: ["lat", "lon"]
     result.op: "avg"
     result.reduced_dims: ["time"]
3) Report: "120-month time-mean SST; remaining dims (lat, lon).
   Min/max from result envelope."
```

## Worked example — every-other-month subsample

User: "Give me every other monthly snapshot from index 0 through
the last one."

```text
1) inspect("monthly.nc")
   → time dim size = 120
2) read_slice(
     "monthly.nc", variable="ssh",
     index_selectors={"time": [0, 119, 2]})
   → result.values: shape (60, ...)
3) Report: "60 timesteps selected (every other month, indices
   0..118)."
```

## Worked example — CDL dump

User: "Dump the CDL of `model_out.nc` so I can see the schema."

```text
1) dump_cdl("model_out.nc", header_only=True)
   → result.cdl: full CDL header (dims + vars + attrs)
2) Echo result.cdl to the user in a code block.
```

If the user wants the data section too, omit `header_only`.

## Pitfalls

- **Stop is inclusive, not exclusive.** Python slices are
  stop-exclusive (`arr[0:5]` → 5 items); `index_selectors` and
  ncks `-d` are stop-inclusive (`[0, 4]` → 5 items). When in
  doubt, eyeball the result shape.
- **Stride-arithmetic surprises.** `[0, 11, 2]` produces 6
  items (0,2,4,6,8,10), not 5. `(stop-start) // stride + 1`.
- **Reduce on a non-existent dim is rejected.** Validate the
  dim spelling against `inspect()` output before calling.
- **`avg`/`sum`/`rms` are not bit-exact vs ncwa.** numpy uses
  pairwise summation; ncwa uses serial. The two diverge at the
  last ULPs (~2e-15 relative). For `min`/`max` they ARE bit-
  exact (no accumulation). If a user disputes a value at the
  15th digit, ncwa is the reference.
- **`dump_cdl` is in-memory.** Multi-GB vars get fully loaded
  before formatting. For huge files, use `header_only=True` or
  filter with `variables=[...]`.
- **CDL text isn't byte-identical to ncks.** Whitespace, float
  precision, and attribute-type-suffix formatting may differ.
  Semantic content (dims, vars, attrs, values after parsing) is
  identical.
- **`reduce_variable` is NaN-propagating.** It uses `np.mean`,
  not `nanmean`. If your variable has NaN fill values, pre-mask
  them or expect NaN in the output.

## Verification

Before declaring an analyze task complete:
- `result.shape` matches what you'd predict from the inputs.
- `result.units` carries through (or you've called this out if
  the input had no units attr).
- For reductions, `result.reduced_dims` lists what you asked
  for and `result.dims` lists what's left.

## See also

- `netcdf-inspect` — must run first
- `netcdf-plot-router` — when the user wants a plot, not array math
- `netcdf-plot-timeseries`, `netcdf-plot-map`, `netcdf-plot-profile` — plot-shaped flows
- Spec: `docs/specs/2026-05-12-cycle-12-ncks-parity.md`

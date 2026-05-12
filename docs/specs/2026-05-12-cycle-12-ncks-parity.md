# Cycle 12 — ncks-parity (hyperslab stride, dim reduction, CDL dump)

> Spec for cycle 12. Adds three ncks-inspired analysis tools to the
> `netcdf-reader` MCP so users can subset, reduce, and dump NetCDF
> files using semantics that are bit-exact identical to NCO's
> `ncks` command. Driven by the user's cycle-end ask: "install ncks
> command... add similar capabilities into netcdf_reader mcp so
> that user can easily analyze the netcdf data. Add tests that
> compares the result from the newly implemented netcdf
> calculations to the result from ncks, which should be
> identical."

## 0. Why this spec is shaped this way

The cycle 1-11 MCP surface is geared toward **plotting workflows**:
inspect → resolve → read a small slice → render. The selectors are
domain-aware (`time="last"`, `lat="40:60"`, `region="NA"`,
`cell_index=N`) and the output is shaped for renderers.

`ncks` covers a *different* workflow: **CLI-style analysis**. Power
users want to grab "every other timestep of variable T between
indices 0-100 along dim Y", reduce a 4D var to a 1D time series by
averaging out lat/lon/level, or dump a file's CDL for grep'ing.
These are not plot-shaped operations — they're array-extraction
and aggregation building blocks.

Cycle 12 closes that gap with three new tools, each modeled on a
specific ncks flag family:

| New MCP tool         | ncks analog               | What it does                                                |
|---------------------|---------------------------|-------------------------------------------------------------|
| `read_slice` ext.    | `ncks -d dim,start,end,stride` | Add index-mode hyperslab with stride to existing read_slice |
| `reduce_variable`   | `ncks -y <op> -a <dims>`  | Collapse a variable along named dims via `{avg,min,max,sum,rms,total}` |
| `dump_cdl`          | `ncks --cdl` / `ncks -m`  | Emit CDL text (semantically equivalent to ncgen-compatible CDL) |

The cross-check is the spec's load-bearing claim: for every
hyperslab and every reduction, our output values must be **bit-
exact identical** to `ncks` run on the same inputs. CDL is held
to a weaker bar (semantic equivalence) because text formatting
diverges between tools.

## 1. Scope and success criteria

### Phase shape: single-phase

No library survey (NCO is C, not a Python dep). All work in
existing `src/mcp/netcdf_reader/` + small new helper / tool
modules. TDD red→green→commit per the cycle 5-11 cadence.

### Success criteria

Cycle 12 is successful when all of the following hold:

1. **Hyperslab stride in `read_slice`** — new optional kwarg
   `index_selectors: dict[str, list[int]]` where each entry is
   `[start, stop, stride]` (stop inclusive, matching ncks `-d`
   semantics; stride default 1). Applies along any named dim
   case-insensitively (works on `time`, `lat`, `NCells`, etc.).
   Mutually exclusive with the named-axis selector (`time=`,
   `lat=`, `cell_index=`) on the same dim — passing both is
   `invalid_spec`.
2. **Hyperslab values bit-exact match ncks** — for a synthetic
   fixture with float64 / float32 / int32 / int64 variables, the
   array returned by `read_slice(..., index_selectors={dim:[s,e,st]})`
   equals the array returned by `ncks -d dim,s,e,st -v var
   in.nc out.nc; ncdump out.nc` (parsed) to full precision. At
   least one dim with non-unit stride.
3. **Cross-dim hyperslab** — multiple dims sliced simultaneously
   (e.g. `{time: [0,11,2], lat: [10,40,5]}`) returns the
   Cartesian-product slice; values bit-exact match ncks.
4. **`reduce_variable` MCP tool** — new tool
   `reduce_variable(path, variable, reduce_dims, op, *,
   mesh_path=None)` returns the reduced array. Supported ops:
   `{avg, min, max, sum, rms, total}`. `total` is a ncks-ism
   meaning "sum" (kept for parity). `reduce_dims=[]` reduces
   over all dims to a scalar.
5. **`reduce_variable` values bit-exact match ncks** — for each
   op in {avg, min, max, sum, rms} on a synthetic fixture:
   our output equals `ncks -y <op> -a <dims> -v var in.nc out.nc`
   then re-read. Float comparison uses `np.array_equal` (bit-
   exact), not `allclose` — the spec is "identical", not "close".
6. **`dump_cdl` MCP tool** — new tool `dump_cdl(path, *,
   variables=None, header_only=False)` returns a JSON envelope
   with `result.cdl` containing CDL text. When `variables`
   supplied, restricts to that subset (parallels `ncks -v` +
   `--cdl`). `header_only=True` omits the `data:` section
   (parallels `ncks -m` / `ncdump -h`).
7. **CDL semantic equivalence** — for a synthetic fixture, the
   CDL produced by our `dump_cdl` and by `ncks --cdl` parse to
   the same logical structure (same variables, same dims, same
   attribute key/value pairs, same data values). Whitespace and
   formatting differences are allowed; structural differences
   (missing var, wrong dim size, attribute mismatch) fail the
   test.
8. **MCP server surface count** — `list_tool_names()` returns 12
   (was 10 after cycle 11). Two new tools: `reduce_variable`,
   `dump_cdl`. (`read_slice` is extended, not new — the tool
   list doesn't change for its addition.)
9. **Skill docs updated** —
   `netcdf-inspect/SKILL.md` gets a "CDL dump" reference; new
   short skill `netcdf-analyze` describes when to reach for
   `reduce_variable` and `read_slice` hyperslab (vs the plot
   skills). README capability table gains one row.
10. **Gates green** — `pytest -ra`, `ruff check`,
    `mypy src tools tests` all green on the merge commit; no new
    mypy errors beyond the pre-existing yaml-stub baseline.
    ncks-comparison tests `skip` (not fail) when `ncks` is not
    on PATH, so CI without NCO installed still passes.

## 2. Out of scope this cycle

- **Append/concatenate** (`ncks -A`, `ncrcat`, `ncecat`). The
  MCP is read-only by design; writing back NetCDF is a separate
  concern.
- **Attribute editing** (`ncks --att`, `ncatted`). Same reason.
- **NetCDF4 groups** (`ncks -g`). MPAS/Omega flat-file world
  doesn't use them; defer until a real consumer asks.
- **Record dimension surgery** (`--mk_rec_dmn`, `--no_rec_dmn`,
  `--fix_rec_dmn`). NCO-specific concept; not a plotting
  blocker.
- **Auxiliary-coordinate bounding** (`ncks -X
  lon_min,lon_max,lat_min,lat_max`). Cycle 3 already ships
  rectilinear bbox via `lat="lo:hi"` / `lon="lo:hi"`; cycle 11
  ships unstructured via `cells_in_bbox`. ncks `-X` is a third
  spelling of the same thing.
- **CDL emit with `--frm_prn`, `--xml`, `--jsn`** (alternative
  print formats). Standard CDL only.
- **Per-record stride aggregation** (`--mro`, e.g. "average
  each consecutive 3 records"). Different from
  `reduce_variable` (which collapses entire dims). Cycle 13+.
- **Multi-variable extraction** (`-v v1,v2,v3` returning all
  three in one call). Caller can loop. Cycle 13+ if demand
  appears.
- **Packing / unpacking** (`ncks --hdf_unpack`, etc.). Adapter
  layer handles `scale_factor`/`add_offset` already via xarray.
- **CICE / EAMxx cell-axis selectors for `read_slice`** (carry
  from cycle 11 §6). Cycle 13+.

## 3. Affected surface

### 3.1 read_slice — hyperslab stride extension

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/tools/read_slice.py` | New kwarg `index_selectors: dict[str, list[int]] \| None = None`. Each entry is `[start, stop, stride]`. Plumbs through to `resolve_spec` and `_apply_selectors`. |
| `src/mcp/netcdf_reader/tools/resolve_spec.py` | Validate `index_selectors`: each value is a list of 2 or 3 ints (stride optional), `0 <= start <= stop <= dim_size-1`, `stride >= 1`. Dim name resolved case-insensitively against `da.dims`. Mutually-exclusive check against `time/level/lat/lon/cell_index/cell_indices` on the **same dim** (different dims fine). Stored as `resolved["index_selectors"] = {actual_dim_name: [s, e, st]}`. |
| `src/mcp/netcdf_reader/tools/read_slice.py` | `_apply_selectors` honors `resolved["index_selectors"]` via `da.isel({dim: slice(s, e+1, st)})`. The `+1` makes stop inclusive (ncks semantics). |

### 3.2 reduce_variable — new tool

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/tools/reduce_variable.py` (NEW) | `reduce_variable(path, variable, reduce_dims, op, *, mesh_path=None, adapter, ssh_config=None) -> dict`. Opens via adapter, validates `reduce_dims` (each present in `da.dims`, case-insensitively) and `op` in the supported set, then applies the reduction via numpy on the loaded array (xarray's `.mean(dim=)` etc. would also work but numpy keeps the bit-exact arithmetic predictable). Returns envelope with `result.values`, `result.dims` (remaining dims after reduction), `result.shape`, `result.op`, `result.reduced_dims`. |
| ops impl | `avg` = `np.mean` (NaN-preserving — `nanmean` would diverge from ncks; **TBD: verify ncks behavior on NaN**). `sum`/`total` = `np.sum`. `min` = `np.min`. `max` = `np.max`. `rms` = `np.sqrt(np.mean(x*x))`. All single-pass numpy ops on float64-upcast input. |

### 3.3 dump_cdl — new tool

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/tools/dump_cdl.py` (NEW) | `dump_cdl(path, *, variables=None, header_only=False, adapter, ssh_config=None) -> dict`. Uses Python's `netCDF4` library (already a transitive xarray dep) to emit CDL via `Dataset.__repr__`-equivalent traversal, OR shells out to `ncdump -h` if `netCDF4` traversal proves fragile. **First-choice impl**: roll our own CDL writer that walks `xr.Dataset` (dims, vars, attrs, optional data) — full control, no system dep. **Fallback**: subprocess to `ncdump` (always installed alongside `nco`). Spec leaves the choice open; whichever yields semantic equivalence with ncks. |

### 3.4 Server dispatch

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/server.py` | Add `reduce_variable` and `dump_cdl` to `list_tool_names()` and `dispatch()`. Count goes 10 → 12. |
| `src/mcp/netcdf_reader/tools/__init__.py` | Export new modules. |

### 3.5 Tests — unit

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_hyperslab_stride.py` | NEW. `index_selectors` on synthetic fixture: single-dim, multi-dim, stride=1 (default), stride=N, validation errors (bad bounds, negative stride, same-dim conflict with named selector). |
| `tests/mcp/netcdf_reader/unit/test_reduce_variable.py` | NEW. Each op on synthetic 4D var: avg/min/max/sum/rms/total. Reduce-all-dims → scalar. Reduce-one-dim → 3D. Bad op name → invalid_spec. Bad dim name → invalid_spec. |
| `tests/mcp/netcdf_reader/unit/test_dump_cdl.py` | NEW. `dump_cdl` on synthetic fixture: full CDL contains expected dim declarations, var declarations, attr lines, data section. `header_only=True` omits data. `variables=[...]` restricts. |
| `tests/mcp/netcdf_reader/unit/test_server.py` | UPDATE. Tool count 10 → 12. |
| `tests/targets/claude_code/test_mcp_smoke.py` | UPDATE. Expected tool count 10 → 12. |

### 3.6 Tests — ncks comparison (the load-bearing tests)

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/integration/test_ncks_parity.py` | NEW. Module-level `pytest.importorskip` / `shutil.which("ncks")` skip when ncks not on PATH. Helper `_ncks_extract(infile, outfile, *args)` runs ncks via subprocess. Three parametrized tests: **(a) hyperslab parity** — for each of (single-dim no-stride, single-dim stride=2, multi-dim mixed strides), assert `read_slice` array `np.array_equal` to ncks output array. **(b) reduce parity** — for each op ∈ {avg, min, max, sum, rms}, assert reduction matches ncks `-y <op> -a <dim>` output. **(c) CDL parity** — parse our CDL and ncks's `--cdl` output through a normalizer (strip whitespace/comments; collect dims/vars/attrs/data into Python dicts); assert dict equality. |

### 3.7 Skills + docs

| File | Change |
|---|---|
| `src/skills/netcdf-inspect/SKILL.md` | Add a "Need ncks-style CDL dump?" pointer to `dump_cdl`. |
| `src/skills/netcdf-analyze/SKILL.md` (NEW) | Short skill that orients users: "when the request is array math (subsetting / reducing) and not a plot, use these three tools". Three-row table mapping ncks flags → our tools, with quick examples. |
| `README.md` | Capability table: add "ncks-style analysis (hyperslab + dim reduction + CDL dump) — shipping (cycle 12)". |

## 4. Cross-cutting principles

1. **Bit-exact identity is the contract.** "Similar" is not the
   bar. Test asserts use `np.array_equal`, not `np.allclose`.
   If a particular dtype or op can't hit bit-exact (e.g. RMS
   on float32 due to op-order differences), document the
   exception and use a tight tolerance for that case only.

2. **ncks-comparison tests skip, don't fail, when ncks is
   absent.** `shutil.which("ncks") is None` → skip with a clear
   reason. Local dev without NCO installed still gets a green
   gate.

3. **Adapter-agnostic.** New tools take the same `adapter`
   parameter as cycles 1-11. Works for local files, SSH paths,
   globs (when the path classify returns a single open
   dataset). Multi-file glob support for `reduce_variable` is
   nice-to-have; spec'd as "works when classify returns one
   ds via mfdataset, errors cleanly otherwise".

4. **No new third-party deps.** numpy + xarray + netCDF4 cover
   everything. ncks is invoked via subprocess only in tests.

5. **Backwards compatibility.** All extensions to `read_slice`
   are optional kwargs; existing callers see no change. Cycle
   3-11 tests stay green.

6. **TDD red→green→commit per cycle 5-11 cadence.** One task
   = one commit with its tests.

## 5. Open risks

- **NaN handling divergence.** ncks `-y avg` policy on NaN /
  missing values may or may not match `np.mean`. Mitigation:
  spec-time empirical check with a fixture containing NaN; if
  divergence, our `reduce_variable` matches xarray's
  `nanmean`-style behavior and the ncks-comparison test uses
  a NaN-free fixture for the bit-exact assertion. Add a NaN
  fixture as a separate `xfail` case to document the
  divergence.

- **CDL precision formatting.** ncks emits floats with
  10-digit-ish precision by default; we may emit full
  `repr()` (17 digits for float64). Both round-trip to the
  same float, but the text differs. Mitigation: CDL test uses
  a *semantic* comparator that parses values back to numbers
  and compares numerically.

- **Stride semantics edge case.** `ncks -d dim,0,10,3` →
  indices 0,3,6,9 (stop exclusive in the stride sense).
  Verify against ncks: does `stop` mean "last index allowed"
  (inclusive) or "stop here, don't include" (exclusive)?
  Mitigation: spec-time check; document and match whichever
  ncks does. (Best guess: inclusive; ncks docs say "min and
  max are inclusive".)

- **Mixing index_selectors with cell_index.** If user supplies
  both `index_selectors={"NCells": [0,99,2]}` AND
  `cell_index=5`, that's a same-dim conflict. Resolve_spec
  should reject as `invalid_spec`. Test covers it.

- **dump_cdl roll-your-own vs subprocess.** xarray's
  `Dataset.__repr__` is not CDL. `netCDF4.Dataset` has
  attributes but no built-in CDL emit. Rolling a writer
  requires care with attr-type spelling (`:units = "K"` for
  string vs `:scale_factor = 1.0` for float). If it gets
  hairy, fall back to subprocess to `ncdump -h` (or `ncdump
  file.nc`) and call it done. Spec leaves the choice open;
  task-3 commit message records which won.

- **Large array memory.** `reduce_variable` loads the variable
  fully before reducing. For multi-GB vars this is bad;
  defer chunked reduction (dask) to cycle 13+. Document the
  in-memory limitation in the skill.

## 6. Out-of-scope follow-ons (cycle 13+ candidates)

- **Per-record stride aggregation** (`ncks --mro`).
- **Multi-variable extraction** in one `read_slice` call.
- **CICE / EAMxx cell-axis selectors** for `read_slice` /
  `reduce_variable`.
- **Dask-backed chunked reduction** for `reduce_variable` on
  large vars.
- **NCO operator family parity beyond ncks**: ncwa, ncra, ncbo
  (binary operators), ncea (ensemble mean). Each is a
  cycle-sized piece on its own.
- **CDL emit in alternative formats**: XML (`--xml`) or JSON
  (`--jsn`).
- **Auxiliary-coordinate `-X` bbox** as a unified spelling.
- Carry-overs from cycle 11 §6 (multi-cell overlay, cross-
  sections, named region lookup on unstructured, etc.).

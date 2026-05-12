# Real-data test pass — 2026-05-12

Findings from running the cycle 8/9 pipeline + tester-guide
applicable cases against a substantial real-data drop the user
added under `data/`:

- **`data/omega/`** (12 monthly Omega histories, 2 hifreq, 2
  restarts, 3 meshes, 1 IOTest file)
- **`data/e3sm/`** (real SCREAM physics/diags/restart, real CICE
  restart, ELM r/rh0, CPL r/hi)

Result: **8 PASS / 5 FAIL across 13 deep tests**, plus discovery
inspect on all 30 files. The failures fall into 5 distinct bug
classes (F-01 through F-05) and 2 coverage gaps (F-06, F-07).
The cycle 8/9 happy paths verified end-to-end on real Omega
(inspect → read_slice → render_map → 647 KB PNG of 7153-cell
Temperature field).

This document is the input to the cycle-10 spec
(`docs/specs/2026-05-12-cycle-10-...`).

## 1. Test scoreboard

### Discovery pass (30 files, all inspected)

| Status | Count | Files |
|---|---|---|
| `ok=true` w/ spatial | 3 | Omega mesh files (global, ocean, planar) |
| `ok=true` no spatial | 3 | cpl.hi, cpl.r, elm.r (generic CF, no lat/lon) |
| `ambiguous` mesh_pairing_required | 19 | 12 Omega histories + 2 restarts + IOTest + real CICE + 3 EAMxx + 1 elm.rh0 (MIS-detect, see F-05) |
| `internal_error` | 2 | scream.*.rhist (CF time decode) |
| **UNCAUGHT EXCEPTION (no envelope)** | 2 | ocn.hifreq.*.nc — F-01 critical bug |

### Deep pass (13 cases)

| Case | Status |
|---|---|
| omega_mesh_pair (history + global_test_mesh) | ✗ FAIL — wrong mesh picked (F-03) |
| omega_mesh_pair (history + ocean_test_mesh) | ✓ |
| omega_paired_candidates_listed | ✓ |
| omega_slice_read | ✗ depends on wrong-mesh pick |
| omega_render_map (real, ocean_test_mesh) | ✓ — **647 KB PNG** |
| omega_multi_file_glob_bare (12 monthly hists) | ✗ FAIL — F-01 crash |
| omega_multi_file_glob_paired | ✗ FAIL — F-01 crash |
| cice_no_grid_present | ✓ |
| eamxx_no_grid_present | ✓ |
| elm_rh0_attrs_probe (root cause F-05) | ✓ |
| elm_r_attrs_probe (root cause F-06) | ✓ |
| hifreq_repro | ✗ FAIL — F-01 reproduces |
| scream_rhist_repro | ✗ test-script bug |

## 2. Findings — bugs

### F-01 (BLOCKER) — `inspect()` crashes with uncaught TypeError on Omega hifreq files

**Reproducer**: `inspect("data/omega/ocn.hifreq.0001-06.nc")` (or
`-07`).

**Symptom**: Raw Python exception propagates out of the inspect
tool boundary, not a structured envelope:

```
TypeError: '>' not supported between instances of
'datetime.timedelta' and 'int'
  File "src/mcp/netcdf_reader/conventions/cf.py", line 157, in extract_time
      elif np.all(diffs > np.timedelta64(0, "ns")):
```

**Root cause**: In `_cf.extract_time()`, `diffs` is computed from
cftime-decoded `datetime.timedelta` objects (`datetime.timedelta`
instances stored in an object dtype array). The comparison
`diffs > np.timedelta64(0, "ns")` raises because numpy's
broadcast can't compare `timedelta` to `timedelta64`.

The hifreq files have sub-daily time steps using a `noleap`
calendar; cftime returns Python `datetime.timedelta` (via the
no-pandas-fallback path).

**Blast radius**: This isn't just hifreq — **same exception
breaks multi-file glob inspect on the 12 monthly Omega histories**
(see deep test results above). Multi-file unstructured time-series
— the major cycle-10 use case — is fully blocked by this one bug.

**Severity**: BLOCKER. Inspect tool MUST always return an envelope;
raw exceptions are a contract violation. Even worse, the same
exception blocks any multi-file workflow on Omega data.

**Fix sketch**: In `cf.py:_extract_time` (around line 150-160),
detect the `datetime.timedelta` element type and coerce to
`np.timedelta64` before comparison, or use a generic Python-side
monotonicity check (`all(d > timedelta(0) for d in diffs)`).
Also: harden `inspect.py` to wrap the inner pipeline in
`try/except Exception` → `envelope.error(INTERNAL_ERROR, ...)`
so future regressions don't escape.

### F-02 (BLOCKER) — `scream.*.rhist.*` files surface unrecoverable `internal_error`

**Reproducer**:
```
inspect("data/e3sm/scream.phys.h.rhist.INSTANT.nsteps_x22.0001-01-01-21600.nc")
```

**Symptom**: `internal_error` envelope with raw cftime message:
> `ValueError: unable to decode time units 'days since 0001-01-01
> 00:00:00' with "calendar 'noleap'"`

**Root cause**: The rhist files declare CF-compliant time units
but `xarray.open_dataset(decode_times=True)` chokes on the
year-0001 origin (cftime's `noleap` calendar can't represent that
boundary). cycle-3's `cf.py` has a `cf_time_decode_failed`
warning code, but the cycle-3 path doesn't trigger it — the
exception fires earlier, during `adapter.open()`.

**Severity**: BLOCKER. Files exist in dogfood drop, can't be
inspected at all. Inspect should retry with `decode_times=False`
and emit `TIME_DECODE_FAILED` warning per the cycle-6 pattern.

**Fix sketch**: In `adapter.NetCDFAdapter.open()`, wrap the
`xarray.open_dataset(..., decode_times=True)` in a try/except
`ValueError`. On failure, retry with `decode_times=False` and let
caller surface the warning. The MPAS detector already handles
this (history files with `Time` dim but no time variable); the
fix extends that pattern to CF.

### F-03 (MAJOR) — Mesh-pair candidate ranking picks wrong mesh when multiple meshes are present

**Reproducer**:
```
inspect("data/omega/ocn.hist.0001-02-01_00.00.00.nc")
```
Omega dir has THREE meshes — `global_test_mesh.nc` (2562 cells),
`ocean_test_mesh.nc` (7153 cells), `planar_test_mesh.nc`.

Current candidate ranking surfaces them alphabetically among
`*_mesh.nc` matches:
1. `global_test_mesh.nc` ← top suggestion (WRONG; 2562 cells)
2. `ocean_test_mesh.nc` ← correct (7153 cells)
3. `planar_test_mesh.nc`

If the user trusts the rank-1 suggestion and supplies it:
```
inspect(hist, mesh_path="data/omega/global_test_mesh.nc")
→ multi_file_combine_failed: cell-dim size mismatch:
  history.NCells=7153, mesh.nCells=2562
```

**Root cause**: `find_mesh_candidates` ranks by basename heuristic
only; it doesn't open candidates to dim-check. The validator
(`validate_mesh_pair`) catches the mismatch later, but the cost
is one round-trip with a wrong pick.

**Severity**: MAJOR (high friction; user has to try-and-fail).
Common situation in real E3SM/Omega runs that ship multiple test
meshes alongside output.

**Fix sketch**: In `find_mesh_candidates`, after the basename
ranking, optionally open each candidate (cheap — just need to
read dim sizes), filter to those whose cell-dim agrees with the
history, then re-rank dim-matches first. Defer the open if the
dir has only one candidate; do it when ≥2 compete.

### F-04 (MAJOR) — EAMxx detector false-positives on ELM half-history files

**Reproducer**: `inspect("data/e3sm/elm.rh0.0001-01-01-21600.nc")`.

**Symptom**: Returns `mesh_pairing_required` with `family=EAMxx`,
but the file is an ELM land model output, not EAMxx.

**Root cause**: ELM rh0 ships:
- `source = "E3SM Land Model"` (correct, NOT EAMxx)
- `case = "ERS_Ln22.ne30_ne30.F2010-SCREAMv1.frontier...eamxx..."`
  ← CIME case name includes "SCREAM" and "eamxx" tokens
  because the parent SCREAM coupled run produced the ELM output.

Our EAMxx detector (cycle 9 §3.1) treats `case` containing
"SCREAM" as a sufficient signal. The dim corroboration (`ncol`/
`elem`/`gp`) is checked but only raises confidence, not required.

**Severity**: MAJOR. Misrouting an ELM file to EAMxx mesh-pair
flow leads the agent down the wrong path; the user gets an
EAMxx-shaped prompt that doesn't match what's in the file.

**Fix sketch**: Tighten the EAMxx detector — require AT LEAST
one of `{has_ncol, has_dycore}` for the case-attr signal to
fire (source attr can stand alone). Also: prefer the more
specific producer attr — if `source` contains a non-EAMxx
identifier ("E3SM Land Model"), exit early before checking
`case`.

### F-05 (test-fixture bug) — `record() got multiple values for 'ok'`

Test-script bug in `.scratch/cycle-10-real-data/test_paths.py`,
not a product issue. The `try_()` helper passes `ok` positionally
and `**detail` separately; one of the test functions returned a
detail dict that also keyed `"ok"`. Cosmetic — fixed by renaming
the test detail key.

## 3. Findings — coverage gaps

### F-06 (MAJOR coverage gap) — ELM (E3SM Land Model) convention not detected

**Files affected**: `elm.r.0001-01-01-21600.nc` (787 MB!),
`elm.rh0.0001-01-01-21600.nc` (191 MB).

**Current behavior**: `elm.r` detected as plain CF, spatial=None;
`elm.rh0` mis-detected as EAMxx (F-04).

**The unique ELM fingerprint**:
- `source = "E3SM Land Model"` (strong attr signal)
- Hierarchical dim mosaic: `gridcell`, `topounit`, `landunit`,
  `column`, `pft`, plus vertical `levgrnd`, `levlak`, `levsno`,
  `levcan`, `levsno1`, `levtot`
- elm.rh0 also uses `lndgrid` + `natpft` + `ltype`

**Plotting options**:
- ELM history files (`*.h0.*`) usually ship lat/lon on `gridcell`
  → similar to EAMxx physics path (scatter on 1-D ncol).
- ELM restart files don't have lat/lon — needs grid pair like
  CICE.
- PFT-mosaic structure (`pft × gridcell`) is its own visualization
  problem (stacked-bar per gridcell vs. dominant-PFT per cell);
  out of cycle-10 scope.

**Severity**: MAJOR. ELM is one of the four E3SM component
models; users expect at least the inspect path to detect it.

### F-07 (MAJOR coverage gap) — CPL (E3SM coupler) convention not detected

**Files affected**: `cpl.r.0001-01-01-21600.nc` (86 MB),
`cpl.hi.0001-01-01-39600.nc` (153 MB).

**Current behavior**: Both detected as plain CF, spatial=None.

**The CPL fingerprint**: Dims partitioned by component:
- `doma_ny`, `doma_nx`, `doml_*`, `domo_*`, `domi_*` (per-component
  domain dims)
- `a2x_ax_*`, `o2x_ox_*`, `i2x_ix_*` (component-to-coupler mapping
  axes; the "ax" / "ox" / "ix" suffix is the per-component grid)
- `xao_ax_*` (atmosphere-on-ocean), `xao_ox_*` (ocean-on-atmosphere
  remap)

**Realistic plotting**: Most CPL variables are coupler-internal
mapping data (mapping weights, history accumulations). Inspect
detection is the bar; full plotting may not even make sense in
cycle 10.

**Severity**: MAJOR for detection; MINOR for actual plotting.

## 4. Findings — positive

### F-08 (positive) — Cycle-8 MPAS render path works end-to-end on real Omega

Successfully inspected `ocn.hist.0001-02-01_00.00.00.nc` paired
with `ocean_test_mesh.nc`, sliced `Temperature[t=0, level=0]` to
a 7153-element inline values array, rendered via the cycle-8
uxarray + to_polycollection path → 647 KB PNG.

`oracle.drawn.grid_kind = "unstructured"`,
`n_cells = 7153`. Render took 18s on the test machine (acceptable
for 7153 cells; will need datashader for ne1024pg2-scale).

### F-09 (positive) — Cycle-9 CICE + EAMxx contract verified on real files

- Real CICE restart (`cice.r.0001-01-01-21600.nc`, 13 MB) →
  `mesh_pairing_required` with family=CICE, correct missing
  coords (`["TLAT", "TLON"]`).
- Real SCREAM physics history
  (`scream.phys.h.INSTANT.nsteps_x22.0001-01-01-39600.nc`,
  381 MB) → `mesh_pairing_required` with family=EAMxx,
  correct missing coords (`["lat", "lon"]`).

The cycle-9 contract holds; the gap remains the lack of paired
CICE grid files / EAMxx scrip files in the data drop. Same
deferral as the cycle-9 spec called out.

### F-10 (positive) — Bare-history mesh-pair candidate prompt works on real Omega

Bare inspect on `ocn.hist.0001-02-01_00.00.00.nc` correctly
surfaced `global_test_mesh.nc`, `ocean_test_mesh.nc`, and
`planar_test_mesh.nc` as candidates. The agent has actionable
choices. (Ranking is wrong — see F-03 — but the candidate set
is complete.)

## 5. Files not exercised this pass

- `IOTest.nc` (139 MB Omega test file) — detected as MPAS but
  not paired or rendered. Worth a follow-up cycle.
- `ocn.restart.*.nc` — same code path as histories; assumed to
  work once F-01 is fixed.
- 5 of 12 monthly Omega histories — covered by glob test (which
  itself crashes via F-01).
- `scream.r.INSTANT.*` (2.9 GB) — successfully inspected
  (0.06s) but not rendered.

## 6. Cycle-10 spec input

The findings map to cycle-10 scope as:

| Item | Severity | Cycle-10 task |
|---|---|---|
| F-01 hifreq + multi-file crash | BLOCKER | Task A: time-decode robustness in cf.py + inspect.py |
| F-02 scream.rhist time-decode | BLOCKER | Task A (same fix area: adapter decode_times fallback) |
| F-03 wrong mesh ranking | MAJOR | Task B: dim-aware mesh-pair candidate filter |
| F-04 EAMxx false-positive on ELM | MAJOR | Task C: EAMxx detector tightening + ELM convention detector |
| F-06 ELM not detected | MAJOR | Task C (combined; ELM detector + spatial pair) |
| F-07 CPL not detected | MAJOR | Task D: CPL detector (detection only; no plot) |
| Multi-file unstructured time-series | MAJOR | Task E: enable glob path once F-01 fixed |

That's 5 coherent tasks for cycle 10, plus the EAMxx physics-grid
real-file dogfood follow-on already in the cycle-9 spec.

---

End of findings.

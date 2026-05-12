# Cycle 10 — Robustness fixes + E3SM component coverage

> Spec for the next cycle, driven by findings from the 2026-05-12
> real-data test pass against the user's data drop
> (`data/omega/` + `data/e3sm/`). See
> `docs/research/2026-05-12-cycle-10-real-data-findings.md` for the
> finding-by-finding details that motivate each task here.

## 0. Why this spec is shaped this way

The cycle-8/9 pipeline cleared the synthetic-fixture tests and
real-file Omega (MPAS family). The real-data drop the user added
on 2026-05-12 surfaced **two BLOCKER bugs** and **two MAJOR
coverage gaps** that cycle 10 must fix before cycle 9 can be
considered shipping-ready:

- **F-01 (BLOCKER)**: `inspect()` raises an uncaught Python
  `TypeError` on Omega hifreq files AND on multi-file globs of
  monthly Omega histories. The multi-file unstructured
  time-series workflow — the highest-value cycle-10 use case — is
  fully blocked.
- **F-02 (BLOCKER)**: SCREAM rhist files fail with
  `internal_error` because xarray's `decode_times=True` can't
  parse the year-0001 origin under `noleap` calendar.
- **F-03 (MAJOR)**: When the history's directory has multiple
  candidate meshes, our candidate ranking surfaces them
  alphabetically — picking the wrong one for the user's
  most-likely-correct flow.
- **F-04 (MAJOR)**: EAMxx detector false-positives on ELM
  `*.rh0.*` files whose CIME `case` attribute contains "SCREAM"
  even though `source = "E3SM Land Model"`.
- **F-06/F-07 (MAJOR)**: ELM (E3SM Land Model) and CPL (coupler)
  files flow through as generic CF with `spatial=null` — no
  convention-specific detection.

These are tightly related. F-01 and F-02 are the same area of
code (time-decode robustness in `cf.py` + `adapter.open()`).
F-04 and F-06 both need ELM detection (F-06) and EAMxx
tightening (F-04). F-03 is a focused fix in `mesh_pair.py`.

Cycle 10 takes a **single-phase** shape — no library survey;
all changes are inside existing modules.

## 1. Scope and success criteria

### Phase shape: single-phase

Implementation work spans 5 tasks (A → E), each TDD red→green→
commit + tests, mirroring the cycle-8/9 cadence. No new
third-party dependencies. No new render path.

### Success criteria

Cycle 10 is successful when all of the following hold:

1. **F-01 fixed**: `inspect("data/omega/ocn.hifreq.0001-06.nc")`
   returns a valid envelope (either `ok=true` with `time=null`
   + `TIME_DECODE_FAILED` warning OR `ok=false` with structured
   error). NO uncaught Python exception.
2. **F-01 fixed for multi-file**:
   `inspect("data/omega/ocn.hist.000*-*-01_00.00.00.nc",
   mesh_path="data/omega/ocean_test_mesh.nc")` returns
   `ok=true`, `result.kind = "local_multi"`, files list contains
   all 13 files (12 monthly + cross-year Jan 0002), spatial
   populated from the paired mesh, time range spans all months.
3. **F-02 fixed**:
   `inspect("data/e3sm/scream.phys.h.rhist.INSTANT...nc")`
   returns `ok=true` with `time` either populated or null + a
   `TIME_DECODE_FAILED` warning. NO `internal_error`.
4. **F-03 fixed**: bare inspect on an Omega history with multiple
   sibling meshes returns candidates ranked so that the
   dim-matching mesh (`ocean_test_mesh.nc`, 7153 cells) appears
   first, NOT alphabetically (`global_test_mesh.nc`, 2562 cells).
5. **F-04 fixed**: `inspect("data/e3sm/elm.rh0...")` is NOT
   detected as EAMxx (no false positive).
6. **F-06 ELM detector ships**: `inspect("data/e3sm/elm.r...")`
   returns `convention.primary = "ELM"` (or `"E3SM-ELM"`),
   evidence cites `source` + dim fingerprint. `spatial = null`
   is acceptable (PFT mosaic plotting is cycle 11+).
7. **F-07 CPL detector ships**: `inspect("data/e3sm/cpl.r...")`
   returns `convention.primary = "CPL"` (or `"E3SM-CPL"`),
   evidence cites the `[a-z]2[a-z]_[a-z]x_n[xy]` dim-pattern
   fingerprint. `spatial = null` acceptable.
8. **`inspect()` boundary hardened**: the inspect tool's inner
   pipeline is wrapped in `try/except Exception` →
   `INTERNAL_ERROR` envelope. NO raw exceptions can escape; the
   F-01 class of regression cannot recur silently.
9. **Multi-file unstructured time-series end-to-end**: with the
   paired mesh, glob the 12 Omega histories, slice a single
   variable across all timestamps, render a time-series PNG.
   (This exercises cycle-3 `compute_stats` + `render_timeseries`
   in addition to the cycle-1 multi-file path.)
10. **Gates green**: `pytest -ra`, `ruff check`,
    `mypy src tools tests` are all green on the merge commit.
    No new yaml-baseline beyond what master already has.

## 2. Out of scope this cycle

- **ELM PFT-mosaic visualization**. Stacked-PFT or
  dominant-PFT-per-cell rendering is a separate problem;
  cycle 11+.
- **EAMxx dycore** (still cycle 11+ per cycle-9 §6).
- **CPL plotting**. Most CPL variables are coupler-internal
  mapping data; detection only in cycle 10.
- **CICE U-grid** (cycle 9 §6 deferral stands).
- **Region clipping / contour / streamline on unstructured**
  (cycle 9 §6 deferral stands).
- **Real-file EAMxx-physics render**. Still requires a SCRIP
  grid file the user doesn't have on disk. The cycle-9 deferral
  stands.

## 3. Affected surface

### 3.1 Task A — Time-decode robustness (F-01 + F-02 + #8)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/cf.py` | `extract_time`: detect when `diffs` array element-type is `datetime.timedelta` (object dtype) and coerce to `np.timedelta64` (or use a pure-Python monotonicity check `all(d > timedelta(0))`). |
| `src/mcp/netcdf_reader/adapter.py` | `NetCDFAdapter.open()`: wrap `xr.open_dataset(..., decode_times=True)` in `try/except (ValueError, OutOfBoundsDatetime)`. On failure, retry with `decode_times=False` and stash a flag on the returned dataset so the caller can emit `TIME_DECODE_FAILED`. |
| `src/mcp/netcdf_reader/tools/inspect.py` | Outer `try/except Exception → INTERNAL_ERROR` envelope around the main pipeline (currently only covers `adapter.open()`; the convention dispatch + extract phases are unprotected). Also: surface the new decode-fallback flag as a structured warning. |

### 3.2 Task B — Mesh-pair candidate dim-aware ranking (F-03)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/mesh_pair.py` | New `_rank_candidates_by_dim_match(history_path, candidates)` helper: opens each candidate, checks cell-dim/`ncol`/`nj*ni` agreement with the history, returns candidates re-sorted with dim-matching ones first. Cheap (only reads dim sizes). Called from `find_mesh_candidates` only when ≥2 candidates compete. |
| `src/mcp/netcdf_reader/tools/inspect.py` | `_mesh_pairing_required_envelope`: include a `match_quality` field on each candidate (`"dim_match"`, `"basename_only"`, `"both"`) so the agent can surface why the top candidate is top. |

### 3.3 Task C — EAMxx tightening + ELM detector (F-04 + F-06)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/eamxx.py` | Tighten detector: require AT LEAST one dim corroboration (`ncol` OR `elem+gp`) for the case-attr signal to fire. The source-attr signal can stand alone (since `"E3SM Atmosphere Model (EAMxx)"` is unambiguous). Also: if `source` contains a clearly-different producer (`"E3SM Land Model"`, `"E3SM Sea Ice Model"`), exit early. |
| `src/mcp/netcdf_reader/conventions/elm.py` (NEW) | Detect ELM via `source = "E3SM Land Model"` + dim fingerprint (`gridcell` AND any of `pft`/`landunit`/`column`/`topounit`). Two flavors: `elm.r` (`gridcell` + `pft` + `column`) and `elm.h*` / `elm.rh0` (`lndgrid` + `natpft` + `ltype`). |
| `src/mcp/netcdf_reader/adapter.py` | Register ELM detector in the dispatch chain (`WRF → ROMS → MPAS → EAMxx → ELM → CICE → CF`). ELM comes before CICE so the source-attr signal pre-empts CICE's variable-fingerprint check, which could occasionally false-positive on land-ice vars. |

### 3.4 Task D — CPL detector (F-07)

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/conventions/cpl.py` (NEW) | Detect CPL via dim-pattern fingerprint: regex match `[a-z]2[a-z]_[a-z]x_n[xy]` against ≥3 dim names AND presence of any `dom[ailo]_n[xy]` dim. Also reports the per-component grids. No spatial extraction in cycle 10 (defer). |
| `src/mcp/netcdf_reader/adapter.py` | Register CPL detector. Position: after ELM (CPL's fingerprint is dim-only, weaker than ELM's source attr; ELM should win on ELM files). |

### 3.5 Task E — Multi-file unstructured time-series end-to-end (#9)

Once Task A unblocks multi-file glob, this is mostly a test +
SKILL.md documentation task; the underlying cycle-1
`multi_file_combine` path already works for time-concat across
identical-spatial files.

| File | Change |
|---|---|
| `src/mcp/netcdf_reader/paths/multi_file.py` | Verify the unstructured-glob path: history files share `NCells`/`Time` concat axis; concat should work via `xr.open_mfdataset(..., concat_dim="Time")`. Currently the cycle-1 implementation may assume rectilinear. |
| `src/skills/netcdf-plot-timeseries/SKILL.md` | Add a subsection on time-series plots from unstructured-mesh history globs: inspect glob + mesh_path → resolve a single cell or area-mean → render timeseries. |
| `tests/mcp/netcdf_reader/integration/test_real_files.py` | EXTEND. Add a test that's skipped unless `data/omega/` files are present; with them, asserts the multi-file glob inspect + paired-mesh slice + timeseries render produces a non-trivial PNG. |

### 3.6 Test surface

| File | Status |
|---|---|
| `tests/mcp/netcdf_reader/unit/test_cf_time_decode.py` | NEW. Pin the F-01 fix: synthetic fixture with `datetime.timedelta` `diffs` array → `extract_time` returns sensible result without crashing. |
| `tests/mcp/netcdf_reader/unit/test_adapter_decode_fallback.py` | NEW. Pin the F-02 fix: synthetic CF file with year-0001 noleap origin → adapter opens, returns fallback dataset, emits flag. |
| `tests/mcp/netcdf_reader/unit/test_inspect_exception_safety.py` | NEW. Pin #8: deliberately inject a raising convention detector via monkeypatch → inspect returns INTERNAL_ERROR envelope, not raw exception. |
| `tests/mcp/netcdf_reader/unit/test_mesh_pair_dim_rank.py` | NEW. Pin F-03 fix: directory with `wrong_mesh.nc` (5 cells) + `right_mesh.nc` (12 cells) + a history with 12 cells → `find_mesh_candidates` returns right_mesh first. |
| `tests/mcp/netcdf_reader/unit/test_conventions_eamxx_tightening.py` | NEW. Pin F-04: file with `case` containing "SCREAM" but `source = "E3SM Land Model"` AND no ncol/elem dims → detect returns None. |
| `tests/mcp/netcdf_reader/unit/test_conventions_elm.py` | NEW. ELM detection: gridcell+pft+column fingerprint, lndgrid+natpft for rh0 flavor, non-falsing on CF/WRF/ROMS/MPAS/CICE/EAMxx. |
| `tests/mcp/netcdf_reader/unit/test_conventions_cpl.py` | NEW. CPL detection: dim-pattern fingerprint, non-falsing. |
| `tests/mcp/netcdf_reader/integration/test_real_omega_timeseries.py` | NEW. End-to-end multi-file + paired-mesh timeseries on the dogfood data. Skipped if `data/omega/` not present. |

### 3.7 Documentation

| File | Change |
|---|---|
| `README.md` | Capability table: add "E3SM Land Model (ELM) inspect detection — shipping (cycle 10)" + "E3SM Coupler (CPL) inspect detection — shipping (cycle 10)" + "Multi-file unstructured time-series — shipping (cycle 10)". |
| `docs/architecture.md` | Update the convention-chain enumeration in the inspect section. |
| `docs/user-guide.md` | Brief subsection on multi-file unstructured workflows: inspect glob + mesh_path → time-series pipeline. |
| `docs/tester-guide.md` | Add §3.13 (ELM inspect), §3.14 (CPL inspect), §3.15 (hifreq time-decode), §3.16 (rhist time-decode), §10.4 (multi-file Omega timeseries), §14.5 (multi-file unstructured glob with mesh_path). |

## 4. Cross-cutting principles

1. **Reverse the contract violation first.** Task A's `try/except`
   hardening of inspect goes in BEFORE the individual fixes so
   any future regression of the same class produces a structured
   envelope rather than a raw exception.

2. **TDD per cycle 5/6/7/8/9 cadence.** One task = one commit
   with tests. Red → green → commit.

3. **Detection-only is acceptable for cycle 10.** ELM and CPL
   detectors ship without spatial extraction or plot paths. The
   contract: `inspect()` correctly identifies the file's
   producer; downstream plot is cycle 11+.

4. **No new third-party dependencies.** Time-decode fallback
   uses xarray's existing `decode_times=False`. ELM/CPL
   detection is pure xarray dim-name/attr inspection. Mesh-rank
   dim-aware filter is a one-file-open cost per candidate.

5. **Cycle-8/9 paths remain stable.** All existing MPAS / CICE /
   EAMxx tests must stay green. No oracle.drawn.grid_kind label
   changes for those branches.

6. **Multi-file glob assumes time-concat.** The cycle-1
   `multi_file_combine` path is reused; cycle 10 doesn't invent
   new combine semantics. If glob files don't share spatial
   dims, surface as `multi_file_combine` ambiguous (cycle-1
   existing behavior).

## 5. Open risks

- **Multi-file Omega open may be slow.** 12 files × 34 MB =
  ~400 MB. `xr.open_mfdataset` with lazy chunks is fine for
  inspect (just metadata), but a slice across all 13 timestamps
  loads ~30 MB per variable. Acceptable for a single field; user
  may need to pre-pick a region. Document in tester-guide §10.4.

- **ELM hierarchical dims could over-trigger.** `gridcell` is a
  generic-sounding name that other land models might reuse.
  Mitigation: require corroboration (`pft` OR `landunit` OR
  `column`) in addition to `gridcell`.

- **`decode_times=False` flag plumbing.** The decode-fallback
  path needs a way to pass the "I bailed on time decoding"
  signal from `adapter.open` up to `inspect.py`. Options:
  (a) stash an attr on the dataset (`ds.attrs["_metplot_time_decode_failed"]`),
  (b) return a (ds, flags) tuple from `adapter.open()`.
  (a) is less invasive but pollutes the dataset attrs; (b) is
  cleaner but touches every adapter caller. Pick (a) for cycle 10
  with a leading underscore so the namespace is reserved.

- **Hifreq files may have other surprises.** Once F-01 fixed,
  inspect should return a valid envelope, but variable extraction
  might surface its own bugs (e.g., bounds variables, optional
  coords). Treat any new finding as a cycle-10 follow-on.

- **EAMxx tightening may break edge cases.** If a real EAMxx
  file ships only `case` (no `source` and no ncol/elem), our
  tightened detector would miss it. Mitigation: real EAMxx
  files always have at least `source = "E3SM Atmosphere Model
  (EAMxx)"`; the tightening only affects derivative files like
  ELM rh0 where `source` clearly says otherwise.

## 6. Out-of-scope follow-ons (cycle 11+ candidates)

- **ELM PFT-mosaic visualization** (stacked-bar per gridcell,
  or dominant-PFT-per-cell maps).
- **ELM spatial pair**: if ELM history files ship lat/lon on
  `gridcell`, that's a 1-D unstructured shape similar to EAMxx
  physics — could reuse the cycle-9 scatter renderer.
- **CPL plotting** (mapping weights heatmap; per-component
  domain visualization).
- **EAMxx physics-grid real-file dogfood** (still pending a
  SCRIP file).
- **CICE U-grid** (cycle 9 §6 carry-over).
- **Region clipping on unstructured** (cycle 9 §6 carry-over).
- **EAMxx dycore** (cycle 9 §6 carry-over).
- **Per-region-overlay timeseries on unstructured** (extends
  Task E with a spatial selector).

## End of spec

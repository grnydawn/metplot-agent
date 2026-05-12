# cycle-6 task 3: Phase A dogfood unblockers (round 2)

**Phase:** A.
**Status:** draft.
**Branch:** `cycle-6-self-improvement-loop` (current).
**Out-of-band:** This task is not in the original cycle-6 plan
(`docs/plans/2026-05-08-cycle-6-self-improvement-loop.md`). It's a
follow-up to `cycle-6 task 2: unblock phase A dogfood`, addressing
three bugs surfaced by Phase A dogfooding on real-world E3SM-class
files (see `docs/research/2026-05-08-cycle-6-dogfood-findings.md`).

## Why this exists

Phase A dogfood inspected three real model files
(`ocn.hist.0001-02-01_00.00.00.nc`, `cice.nc`, `eamxx.nc`,
`ocean_mesh.nc`) plus a synthetic CMIP-style file. Findings doc
recorded three classes of failure in `netcdf-reader.inspect` that
block the dogfood pass from continuing cleanly:

1. **`internal_error` on time-decode** (mesh file, no time variable
   + unusual calendar attr) — contract-violating crash with raw
   Python exception text in the message field. Blocks any further
   dogfooding of MPAS mesh files. See failure_mode finding
   "`netcdf-reader.inspect` raises `internal_error` on MPAS mesh file".
2. **`"MISSING"` placeholder strings preserved verbatim** in
   `standard_name` and `long_name` fields (EAMxx restart) — pollutes
   downstream alias resolution. See failure_mode finding
   "`standard_name` and `long_name` populated with placeholder strings".
3. **`Conventions: MPAS` not recognized** by the convention detector.
   Documented convention used across MPAS-Ocean/-Atmosphere/-Seaice
   and E3SM. Without recognition, downstream skills can't load
   MPAS-specific knowledge. See failure_mode finding
   "`Conventions: MPAS` is not in the convention-detection table".

None of these are refiner-loop targets (the refiner edits skill
markdown, not netcdf-reader source). They have to be fixed by hand
before Phase A can complete a clean sweep on E3SM-flavored files.

## What's NOT in scope here

- **Unstructured-mesh plotting itself** (Voronoi rendering, mesh-history
  pairing in plot path). Deferred to cycle 8 — see Phase A wrap-up
  amendment to cycle-6 spec.
- **Restart-vs-history detection** as a user-facing warning. The
  finding is logged; the implementation is a separate task (could
  bundle into cycle 8 or a cycle-6 task 4 if dogfood reveals more
  pain).
- **MPAS file-pairing logic** (`find_mesh()` tool, sibling-mesh
  discovery). Cycle 8.
- **EAMxx dual-grid handling.** Cycle 8 — bundled with unstructured-mesh
  since dycore-grid handling requires SE/Homme support.

This task is **detect + normalize + don't-crash** only. It surfaces
the right convention name and stops returning garbage; it doesn't
add new plotting capability.

## Files affected

- `src/mcp/netcdf_reader/tools/inspect.py` — time-decode error
  handling, placeholder-string normalization.
- `src/mcp/netcdf_reader/conventions/__init__.py` or
  `src/mcp/netcdf_reader/conventions/<new>.py` — add MPAS branch.
- `src/mcp/netcdf_reader/envelope.py` — possibly add a
  `time_decode_failed` subcode if not already present.
- `tests/mcp/netcdf_reader/unit/test_inspect.py` (and friends) —
  three new test cases.
- `tests/mcp/netcdf_reader/fixtures/` — possibly new tiny fixture
  files (or use synthetic xarray.Dataset constructed inline).

## Steps

### Step 1: Fix the time-decode crash on mesh files

- [ ] **1.1** Reproduce the crash in a unit test. Construct a minimal
  xarray.Dataset with a `Time` dim but no `time` coordinate variable,
  global attr `config_calendar_type: gregorian_noleap`, and `Conventions: MPAS`.
  Write it to a tmp NetCDF, call `inspect(path)`, assert today's
  behavior is `ok: false` with `code: internal_error`. This is the red.

- [ ] **1.2** Trace the failure: it's in the time-decode branch of
  `inspect.py` (or the helper it calls). The error message
  `"input must have type NumPy datetime"` is a numpy/cftime type
  check failing.

- [ ] **1.3** Make the time-decode branch tolerate (a) `Time` dim
  with no corresponding variable → return `result.time = null`,
  (b) calendar attrs the cftime decoder rejects → return `null`
  and add a structured warning, (c) any other decode exception →
  wrap as `time_decode_failed` subcode (NOT `internal_error`).

- [ ] **1.4** Update the red test to assert the new behavior:
  `ok: true`, `result.time = null`, warnings list contains a
  `time_decode_failed`-style entry.

- [ ] **1.5** Add an end-to-end test using the real `ocean_mesh.nc`
  shape (synthetic fixture constructed by xarray, not the user's
  file). Confirms inspect returns `ok: true` and reasonable values
  for variables, dims, spatial (when present).

- [ ] **1.6** Run `pytest tests/mcp/netcdf_reader/` — all green.

- [ ] **1.7** Commit:
  ```
  cycle-6 task 3 step 1: netcdf-reader.inspect tolerates time-decode failures

  Mesh files like ocean_mesh.nc declare a Time dim without a time
  variable and may carry calendar attrs (gregorian_noleap, year-0
  starts) that cftime rejects. Previously the inspect tool crashed
  with internal_error: "input must have type NumPy datetime",
  leaking Python exception text through the response envelope.

  Now: time-decode failures are caught and surfaced as
  result.time = null + a structured time_decode_failed warning.
  inspect returns ok: true with the rest of the file's structure
  populated normally.

  Phase A dogfood: failure_mode finding 'netcdf-reader.inspect
  raises internal_error on MPAS mesh file' addressed.
  ```

### Step 2: Normalize placeholder strings in `long_name` / `standard_name`

- [ ] **2.1** Decide the normalization set: `{"MISSING", "missing",
  "N/A", "n/a", "none", "None", ""}` → `None` (Python `null` in JSON
  envelope). Add as a module-level constant in `inspect.py` (or in
  a helper module if there's a natural home).

- [ ] **2.2** Apply normalization to `standard_name` and `long_name`
  at the variable-summary build step (where `inspect.py` extracts
  per-variable metadata into the result dict).

- [ ] **2.3** Red test: construct an xarray.Dataset with one variable
  having `attrs={"standard_name": "MISSING", "long_name": "MISSING",
  "units": "m"}`. Call inspect, assert the returned variable record
  has `standard_name: null, long_name: null, units: "m"`.

- [ ] **2.4** Add a parametrized variant covering each placeholder
  value in the set above.

- [ ] **2.5** Confirm the existing inspect tests still pass
  (no regression on real CF files where these attrs carry real values).

- [ ] **2.6** Commit:
  ```
  cycle-6 task 3 step 2: normalize placeholder strings in inspect output

  Some writers (e.g. EAMxx) populate standard_name and long_name with
  the literal string "MISSING" instead of omitting the attribute.
  Previously the inspect tool preserved these strings verbatim, which
  pollutes downstream alias resolution — agents tried to match user
  phrases against "MISSING" and got bogus matches.

  Now: a fixed set of placeholder strings (MISSING, missing, N/A,
  n/a, none, None, empty) normalize to null at the inspect output
  layer. Real values pass through unchanged.

  Phase A dogfood: failure_mode finding 'standard_name and long_name
  populated with placeholder strings' addressed.
  ```

### Step 3: Add MPAS to the convention detector

- [ ] **3.1** Read the existing detector layout
  (`src/mcp/netcdf_reader/conventions/`). The CF/WRF/ROMS detectors
  set the pattern for a new `mpas.py` module.

- [ ] **3.2** Create `src/mcp/netcdf_reader/conventions/mpas.py`
  with a detector function that returns `("MPAS", confidence,
  evidence_list)`:
  - **High confidence** (>=0.9): global attr `Conventions == "MPAS"`,
    OR (global attrs `model_name == "mpas"` and `core_name in
    {"ocean", "atmosphere", "seaice"}`), OR (dims include both
    `nCells` AND `nEdges`).
  - **Medium confidence** (~0.6): only one of the dim-name signals
    (`nCells` alone, or `nEdges` alone).
  - **Low confidence** / abstain: no signals.

- [ ] **3.3** Wire the new detector into the convention-selection
  pipeline. Order: CF (if `Conventions` attr matches) → WRF →
  ROMS → **MPAS** → unknown.

- [ ] **3.4** Red test: synthetic dataset with `attrs={"Conventions":
  "MPAS", "model_name": "mpas", "core_name": "ocean"}` plus dims
  `{"nCells": 10, "nEdges": 30, "nVertices": 20}`. Inspect returns
  `convention.primary == "MPAS"`, `confidence == "high"`,
  evidence list mentions the `Conventions` attr.

- [ ] **3.5** Add a "dim-fingerprint-only" test: no `Conventions`
  attr, just `nCells`/`nEdges` dims. Should still detect MPAS at
  high or medium confidence.

- [ ] **3.6** Update the earlier real-file finding: the
  `ocn.hist.*` file previously detected as `CF (low)` should now
  detect as `MPAS (high)` via the dim fingerprint. Add a regression
  test for that shape.

- [ ] **3.7** Run `pytest tests/mcp/netcdf_reader/` — all green.

- [ ] **3.8** Commit:
  ```
  cycle-6 task 3 step 3: add MPAS to convention detector

  Conventions: MPAS is a documented, widely-used convention across
  MPAS-Ocean, MPAS-Atmosphere, and MPAS-Seaice (all of E3SM and
  several CESM components). Previously the inspect tool fell back
  to "unknown" or low-confidence "CF" on these files, blocking
  downstream skills from loading MPAS-specific knowledge.

  Detector logic:
    - high confidence: Conventions attr == "MPAS", OR model_name+
      core_name attrs match, OR both nCells AND nEdges dims present.
    - medium confidence: one of nCells/nEdges dims alone.

  Phase A dogfood: failure_mode finding 'Conventions: MPAS is not
  in the convention-detection table' addressed.
  ```

### Step 4: Update Phase A findings doc with "addressed" markers

- [ ] **4.1** Add a `**Status (2026-05-11):** ADDRESSED by cycle-6
  task 3 step <N>.` line to each of the three findings entries in
  `docs/research/2026-05-08-cycle-6-dogfood-findings.md`. Don't
  delete the entries — they're cycle history.

- [ ] **4.2** Commit:
  ```
  cycle-6 task 3 step 4: mark Phase A findings as addressed

  Three failure_mode entries in the findings doc are now fixed in
  the codebase. Status lines added so the cycle-6 wrap-up audit can
  cross-reference what landed vs what's deferred.
  ```

## Success criteria

- All three findings have a `Status: ADDRESSED` line.
- `pytest tests/mcp/netcdf_reader/` green.
- Re-inspecting `ocean_mesh.nc` returns `ok: true` with
  `convention.primary == "MPAS"`, `confidence == "high"`, and a
  populated `result.time = null` + `time_decode_failed` warning
  rather than the `internal_error` crash.
- Re-inspecting `eamxx.nc` returns variable records with
  `standard_name: null` (not `"MISSING"`) for the affected variables.
- Re-inspecting `ocn.hist.0001-02-01_00.00.00.nc` returns
  `convention.primary == "MPAS"`, `confidence: "high"` (via dim
  fingerprint, since there's no `Conventions` attr).

## Out of scope (recap)

These were tempting to bundle but belong elsewhere:

- **Restart-vs-history detection.** Belongs in `netcdf-inspect/SKILL.md`
  Pitfalls (refiner-addressable) and/or a future cycle-8 task; not
  here because it's a content/UX change, not a netcdf-reader fix.
- **MPAS mesh-history pairing.** Cycle 8 — needs new tool surface.
- **Actual unstructured-mesh plotting.** Cycle 8.
- **CICE convention detection.** Could add but lower priority — no
  `Conventions` attr in CICE files, has to detect by variable-name
  fingerprint, more invasive. Defer until Phase A reveals it's
  urgently blocking.

## Next step after this task

When task 3 ships, Phase A can complete a clean dogfood pass on
the remaining file flavors in the dogfood guide table (ERA5
reanalysis, NOAA OISST, real CMIP6 with proper lat/lon). After
that, Phase A wrap-up:

1. Update `docs/research/2026-05-08-cycle-6-dogfood-findings.md`
   Sign-off section.
2. Amend `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md`
   §6 to add "cycle 8: unstructured-mesh plotting (Omega/MPAS-Ocean
   priority; SE/Homme atmosphere later)" as a top-priority follow-on,
   citing the findings doc.
3. Decide which Phase B applier ops to ship (per the cycle-6 spec's
   plan-revision checkpoint after Task 1).
4. Proceed to Phase B core tasks (plan tasks 2–9).

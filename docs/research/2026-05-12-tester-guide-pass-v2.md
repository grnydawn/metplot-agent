# Tester-guide pass v2 — 2026-05-12 (post-cycle-10)

Programmatic execution of `docs/tester-guide.md` cases reachable
from the on-disk data drop (`data/omega/` + `data/e3sm/`) plus the
legacy fixtures, captured against master at cycle-10 merge head
(`2971987 Merge pull request #15`).

**Result: 31 PASS / 0 FAIL / 0 ERROR.** Every applicable case
passed on first attempt. This is the v2 of the test pass; the v1
pass (2026-05-12 earlier) ran 16 cases and surfaced the 7 findings
that cycle 10 then fixed.

## Headline

The cycle-10 work is **fully verified end-to-end on real data**.
All 7 findings from the v1 pass are now closed:

| Finding | v1 status | v2 status |
|---|---|---|
| F-01 hifreq + multi-file glob TypeError | crashed | ✓ no crash (3.15, 14_bare_glob) |
| F-02 scream rhist internal_error | failed | ✓ no internal_error (3.16) |
| F-03 wrong mesh ranked first | basename-only | ✓ dim-aware (9.3 puts ocean_test_mesh first) |
| F-04 EAMxx false-positive on elm.rh0 | mis-detect | ✓ detects as ELM (3.13b) |
| F-06 ELM undetected | CF fallback | ✓ ELM (3.13a / 3.13b) |
| F-07 CPL undetected | CF fallback | ✓ CPL (3.14a / 3.14b) |
| Multi-file unstructured time-series | crashed (F-01) | ✓ 13-file glob → 12-timestep envelope (14.2) |

## Results table

| Case | Section | Description | Result | Evidence |
|---|---|---|---|---|
| 3.1 | Inspect | Rectilinear CF | ✓ | primary=CF, coord_kind=rectilinear |
| 3.5 | Inspect | Omega ocean_test_mesh.nc | ✓ | unstructured, n_cells=7153 |
| 3.5b | Inspect | Omega global_test_mesh.nc | ✓ | unstructured, n_cells=2562 |
| 3.5c | Inspect | Omega planar_test_mesh.nc | ✓ | unstructured |
| 3.6 | Inspect | Omega history alone (no siblings) | ✓ | ambiguous mesh_pairing_required, candidates=[] |
| 3.7 | Inspect | Omega history with siblings | ✓ | top candidate = ocean_test_mesh (dim-aware F-03) |
| 3.8 | Inspect | Omega paired (history + mesh) | ✓ | n_cells=7153, Temperature=cell_centered |
| 3.9 | Inspect | Missing file | ✓ | file_not_found |
| 3.10 | Inspect | Real CICE restart | ✓ | mesh_pairing_required, family=CICE |
| 3.11 | Inspect | Real SCREAM physics | ✓ | mesh_pairing_required, family=EAMxx |
| 3.12 | Inspect | Cache mtime-keyed | ✓ | 2nd call faster |
| 3.13a NEW | Inspect | ELM restart | ✓ | convention.primary=ELM |
| 3.13b NEW | Inspect | ELM rh0 (F-04 regression) | ✓ | convention.primary=ELM, NOT EAMxx |
| 3.14a NEW | Inspect | CPL restart | ✓ | convention.primary=CPL |
| 3.14b NEW | Inspect | CPL history | ✓ | convention.primary=CPL |
| 3.15 NEW | Inspect | Omega hifreq (F-01) | ✓ | no uncaught exception |
| 3.16 NEW | Inspect | SCREAM rhist (F-02) | ✓ | no internal_error; routes to EAMxx mesh-pair |
| 4.1 | Read slice | Inline (small) | ✓ | form=inline |
| 4.3 | Read slice | Omega paired Temperature | ✓ | shape=[7153], mesh_path echoed |
| 6.1 | Render | Rectilinear + Robinson | ✓ | 245 KB PNG, projection=Robinson |
| 8.1 | Render | **Real Omega unstructured** | ✓ | **647 KB PNG, grid_kind=unstructured, n_cells=7153** |
| 8.3 | Render | MPAS shape mismatch | ✓ | error.code=shape_mismatch |
| 9.3 NEW | Mesh pair | Dim-aware ranking (F-03) | ✓ | ocean_test_mesh ranks before global_test_mesh |
| 9.4 | Mesh pair | Self-exclusion | ✓ | mesh file doesn't list itself |
| 14_bare NEW | Multi-file | Bare glob no-crash (F-01) | ✓ | structured envelope, no exception |
| 14.2 NEW | Multi-file | **Omega 12-file paired glob** | ✓ | **kind=local_multi, n_files=13, time.n=12, n_cells=7153** |
| 20.1 | Failure | file_not_found | ✓ |  |
| 20.2 | Failure | unsupported_path_scheme | ✓ | ftp:// rejected |
| 20.6 | Failure | mesh_pairing_required | ✓ | covered above |
| 20.9 | Failure | multi_file_combine_failed | ✓ | wrong-mesh dim mismatch surfaced |
| 20.10 | Failure | not_4d | ✓ | level= on 3-D variable |

## Cycle-10 features specifically verified

- **A0 — inspect exception-safety harness**: hifreq files no
  longer escape uncaught (3.15).
- **A1 — cf.py timedelta fix**: Omega hifreq processes through
  inspect without crash (3.15); multi-file Omega glob processes
  (14_bare, 14.2).
- **A2 — adapter decode_times fallback**: SCREAM rhist returns
  structured envelope (3.16).
- **B — dim-aware mesh-pair ranking**: ocean_test_mesh wins over
  global_test_mesh as the rank-1 candidate for the matching
  history file (9.3).
- **C1 — EAMxx detector tightening**: elm.rh0 no longer
  false-positives as EAMxx (3.13b).
- **C2 — ELM detector**: elm.r AND elm.rh0 both detect as ELM
  (3.13a, 3.13b).
- **D — CPL detector**: cpl.r AND cpl.hi both detect as CPL
  (3.14a, 3.14b).
- **E — multi-file unstructured time-series**: 12 monthly Omega
  histories + cross-year file + mesh paired into a single
  envelope spanning Feb 0001 → Jan 0002 (14.2).

## Cycle-8/9 contract preserved

- Real Omega Temperature[t=0, level=0] renders to a 647 KB PNG
  via `_render_mpas_voronoi` (`uxgrid.to_polycollection`). Oracle
  reports `grid_kind=unstructured`, `n_cells=7153`,
  `mesh_path=ocean_test_mesh.nc`.
- Bare CICE returns `mesh_pairing_required` with `family=CICE`
  (cycle-9 contract).
- Bare EAMxx returns `mesh_pairing_required` with `family=EAMxx`
  (cycle-9 contract).
- Failure modes all surface as structured envelopes, not raw
  exceptions (cycle-10 A0 harness).

## Files exercised this pass

Real data:
- All 12 Omega monthly histories (one directly, 11 via glob).
- Both Omega hifreq files (no-crash check).
- All 3 Omega meshes (ocean / global / planar).
- Real CICE restart (`cice.r.0001-01-01-21600.nc`).
- Real SCREAM physics (`scream.phys.h.INSTANT...nc`).
- Real SCREAM physics rhist (`scream.phys.h.rhist...nc`).
- Both ELM files (`elm.r.*`, `elm.rh0.*`).
- Both CPL files (`cpl.r.*`, `cpl.hi.*`).

Legacy:
- `.scratch/synthetic_tas.nc` (CF rectilinear).

## Not exercised this pass

Out of scope or requires setup we don't have:

- §1 Installation per host — 7 fresh host environments needed.
- §2 Setup helper on a cartopy-missing system.
- §3.2 CMIP6, §3.3 WRF, §3.4 ROMS — no fixtures of those shapes
  in the data drop.
- §5 Variable & time resolution (alias lookup, fuzzy time) —
  would need a multi-variable file with alias-shaped names.
- §6.5–§6.10 (unknown colormap, vmin/vmax, percentile clip,
  auto-downsample, constant, all-NaN) — covered by unit tests in
  `tests/mcp/plot_renderer/unit/test_render_map.py`.
- §7 WRF & ROMS plotting — no WRF/ROMS files.
- §10 Time-series rendering, §11 Profile — feasible now but
  skipped this pass; cycle-11 follow-on.
- §12 Region clipping (still unstructured-incompatible per
  cycle-9 §6).
- §15 Style by reference — needs vision-capable agent + ref image.
- §16 Remote files — no remote URL or SSH host configured.
- §17 Skill-refiner loop — needs a full agent session.
- §18 Refinement applier — covered by `test_apply_refinements.py`.
- §19 Uninstall + reinstall — would damage the active dev env.

## Outputs generated

- `.scratch/tester-guide-v2/out-rect-robinson.png` (245 KB) —
  synthetic_tas Robinson.
- `.scratch/tester-guide-v2/out-omega-real.png` (647 KB) —
  Omega real Temperature[t=0, level=0] Robinson Voronoi.
- `.scratch/tester-guide-v2/deep_pass.json` — raw row-per-case
  result data.

(All gitignored.)

## Conclusion

The cycle-10 spec's 10 success criteria are end-to-end verified
on real dogfood data. The 7 findings the v1 pass surfaced are all
fixed. The cycle-8/9 contracts hold without regression. The
unstructured time-series workflow (Omega 12 monthly histories +
mesh) is unblocked.

### Recommended next steps

Out-of-cycle-10 items now reachable for a future cycle:

- **§10 Time-series rendering** on the now-paired Omega multi-file
  envelope. Pick a single cell or global area-mean and render
  the 12-timestep series. (Skill stub already shipped in cycle 10
  task E.)
- **§11 Profile rendering** on Omega Temperature[t=0,
  cell=<chosen>, all-levels].
- **EAMxx physics-grid real-file render** — still requires a
  SCRIP file the user doesn't have on disk.
- **ELM/CPL plotting paths** (PFT mosaic, coupler mapping
  weights) — cycle-11+ scope.

---

End of v2 findings.

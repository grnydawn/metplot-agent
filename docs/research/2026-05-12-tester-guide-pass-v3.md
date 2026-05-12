# Tester-guide pass v3 — 2026-05-12 (post-cycle-12)

Programmatic execution of `docs/tester-guide.md` against master
at cycle-12 + tester-guide-§21 head (`8eec229`).

**Result: 47 PASS / 0 FAIL / 0 ERROR on the runnable surface.**

The runnable surface covers every section that can be exercised
from a headless host (no fresh-install loop, no SSH credentials,
no Claude Code Stop hook, no destructive uninstall). The
remaining sections (§1, §15, §16, §17, §19) are stubbed with
"requires interactive host" entries — they need a real
end-user agent run.

Three findings discovered during the pass were **tester-guide
expectation bugs** I authored in the prior PR and have already
been fixed in this same commit (§21.2 envelope shape, §21.12
+ §21.14 dim order). No production-code issues found.

## Headline

The full cycle-3 → cycle-12 surface holds up end-to-end on the
real bundled data. Specifically verified:

- **Cycle-11 time-series** (single cell / regional / global)
  works on the 12-month Omega glob: 47/47 shape & envelope
  checks pass.
- **Cycle-12 ncks parity** on real data: hyperslab is
  **bit-exact identical** to `ncks -d`; reduction matches
  `ncwa -y avg` within `rtol=1e-12`.
- **Cycle-10 convention detection** holds across all four
  E3SM file families (CICE, SCREAM, ELM, CPL) plus the rhist
  time-decode-fallback path.
- **Cycle-12 dump_cdl** produces well-formed CDL (header-only
  + variables filter both behave as documented).

## Headless surface — 47 cases

| Case | Section | Description | Result | Evidence |
|---|---|---|---|---|
| §0 | sanity | server.list_tool_names() count | ✓ | 12 tools |
| §3.1 | inspect | synthetic CF rectilinear | ✓ | primary=CF, coord_kind=rectilinear |
| §3.5 | inspect | MPAS ocean_test_mesh.nc | ✓ | primary=MPAS, n_cells=7153 |
| §3.6/7 | inspect | MPAS history alone | ✓ | mesh_pairing_required, 3 candidates |
| §3.8 | inspect | MPAS paired | ✓ | n_cells=7153, Temperature present |
| §3.9 | inspect | missing file | ✓ | file_not_found |
| §3.10 | inspect | real CICE restart | ✓ | mesh_pairing_required |
| §3.11 | inspect | SCREAM physics | ✓ | mesh_pairing_required |
| §3.13a | inspect | ELM restart (cycle-10) | ✓ | convention.primary=ELM |
| §3.14b | inspect | CPL history (cycle-10) | ✓ | convention.primary=CPL |
| §3.15 | inspect | Omega hifreq (cycle-10 F-01 regression) | ✓ | no exception raised |
| §3.16 | inspect | SCREAM rhist (cycle-10 F-02) | ✓ | no internal_error |
| §4.1 | read_slice | inline small slice | ✓ | form=inline shape=[3,6,8] |
| §4.2 | read_slice | file form (above threshold) | ✓ | form=file, on-disk |
| §4.3 | read_slice | MPAS paired slice | ✓ | shape=[7153], mesh echoed |
| §5.1 | find_variables | hint=sst → tos | ✓ | top match name=tos |
| §5.4 | find_time | iso 2024-01-02 | ✓ | match returned |
| §5.6 | find_time | "first" sentinel | ✓ | matches[0].index=0 |
| §12.2 | regions | custom lat/lon bbox | ✓ | shape narrowed |
| §14.3 | glob | Omega 12-month + mesh | ✓ | kind=local_multi, time.n=12 |
| §20.1 | failure | file_not_found code | ✓ | envelope.error.code=file_not_found |
| §20.4 | failure | ambiguous variable | ✓ | code=ambiguous, subcode=variable |
| §20.6 | failure | mesh_pairing_required | ✓ | subcode=mesh_pairing_required, 3 cand |
| §20.10 | failure | not_4d (3-D var + level) | ✓ | code=not_4d |
| §21.1 | real-data | inspect Omega monthly+mesh | ✓ | n_cells=7153, time.n=1 |
| §21.2 | real-data | inspect 12-month glob+mesh | ✓ | kind=local_multi, time.n=12 |
| §21.3 | real-data | inspect hifreq+mesh | ✓ | time.n=4 |
| §21.4 | timeseries | single-cell, 12 months | ✓ | shape=[12] |
| §21.5 | timeseries | NAtl regional (cells_in_bbox=536) | ✓ | shape=[12, 536] |
| §21.6 | timeseries | global (pre-weight) | ✓ | shape=[12, 7153] |
| §21.7 | timeseries | hifreq glob (Jun+Jul=7 ts) | ✓ | kind=local_multi, time.n=7 |
| §21.8 | profile | single cell, 60 levels | ✓ | shape=[60] |
| §21.9 | profile | find_nearest_cell(lat=30,lon=300)→4705 | ✓ | shape=[60] |
| §21.10 | map | MPAS paired surface temp | ✓ | shape=[7153] |
| §21.11 | hyperslab | time stride [0,3,2] hifreq | ✓ | shape=[2, 7153, 60] |
| §21.12 | hyperslab | top-10 vertical layers | ✓ | shape=[7153, 10] |
| §21.13 | reduce | NCells → cell-mean profile | ✓ | shape=[1, 60], dims=[time, NVertLayers] |
| §21.14 | reduce | time over 12-month glob | ✓ | shape=[7153, 60] |
| §21.15 | dump_cdl | mesh header_only | ✓ | 31201 chars, no data section |
| §21.16 | dump_cdl | Temperature filter | ✓ | T present, S absent |
| §21.17 | parity | **ncks hyperslab on real data** | ✓ | **np.array_equal — bit-exact** |
| §21.18 | parity | **ncwa reduce on real data** | ✓ | **rtol=1e-12 match** |
| §21.19 | e3sm | CICE detect | ✓ | mesh_pairing_required |
| §21.20 | e3sm | SCREAM phys detect | ✓ | mesh_pairing_required |
| §21.21 | e3sm | SCREAM rhist (no crash) | ✓ | no exception |
| §21.22 | e3sm | ELM detect | ✓ | convention.primary=ELM |
| §21.23 | e3sm | CPL detect | ✓ | convention.primary=CPL |

## Findings — tester-guide expectation bugs (all fixed in-PR)

These are bugs in `§21.*` expectations I introduced in PR #20.
The MCP tools behave correctly; the guide had wrong expectations.
Fixed in the same commit that wrote this report.

| Finding | Section | Was (wrong) | Is (correct) |
|---|---|---|---|
| F-V3-01 | §21.2 | `n_files = 12` | `len(result.files) = 13` (12 monthly + 1 mesh included in the file list) |
| F-V3-02 | §21.12 | `shape = [10, 7153]` (NVertLayers first) | `shape = [7153, 10]` — on-disk dim order is preserved by `read_slice` |
| F-V3-03 | §21.14 | `shape = [60, 7153]` (NVertLayers first) | `shape = [7153, 60]` — same dim-order rule |

The dim-order surprise (F-V3-02 / F-V3-03) is the kind of
mistake a tester would make if they reasoned from "natural"
plot-axis order (`vertical × horizontal`) rather than the
on-disk axis tuple from `inspect()`. Worth a callout in the
§21 preamble; not done in this pass to keep scope tight.

## Interactive surface — stubbed

These sections require a real end-user agent run, an SSH host,
or a destructive operation. They are skipped in v3 with the
intent of being verified during the next dogfood-tester pass
inside Claude Code.

| Section | Description | Why stubbed | Smoke check done |
|---|---|---|---|
| §1.1–1.8 | Fresh install on 7 hosts | Each needs a clean host + manual `/plugin marketplace add` | none |
| §2.1 | Setup on a clean machine | Needs a `.venv`-less host | `--help` + `--dry-run` work; reports 4/4 steps |
| §2.2 | Setup idempotency | Needs re-run on populated host | n/a |
| §2.3 | Setup --no-cartopy / --no-scipy | Opt-out flag plumbing | `--help` shows both flags |
| §6.1–6.10 | Rectilinear map render variants | Render produces PNG; verifying the actual PNG content requires visual check | n/a (covered by 1169 pytest cases) |
| §7.1–7.4 | WRF/ROMS map renders | Same | n/a (covered by pytest) |
| §8.1–8.5 | MPAS map renders | Same | n/a (covered by pytest) |
| §9.1–9.5 | Mesh-pairing UX flow | Needs agent to surface candidates and accept user choice | candidate ranking covered (§3.6/7 pass) |
| §10.1–10.3 | Rectilinear timeseries | Render PNG | n/a (covered by §21.4–7 for unstructured + pytest for rectilinear) |
| §11.1–11.3 | Rectilinear profile | Render PNG | n/a (covered by §21.8–9 for unstructured) |
| §13.1–13.4 | Vertical level selection variants | Renders + envelope checks | partial (level= path exercised in §4.3 + §21.10) |
| §15.1–15.3 | Style by reference | Needs reference image upload to agent | none |
| §16.1–16.4 | SSH / HTTPS remote files | Needs network creds | none |
| §17.1–17.3 | Skill-refiner loop | Needs Claude Code session + Stop hook | refinement-applier CLI verified (§18 stub below) |
| §18.1 | List pending refinements | CLI tool | ✓ `tools.apply_refinements --list` → "no pending refinements" |
| §18.2–18.7 | Apply refinements / atomic write | Needs a draft refinement on disk | smoke: `--help` + `--list` work |
| §19.1–19.3 | Uninstall + clean reinstall | Destructive (plugin uninstall, dir wipe) | none |
| §20.7–20.9 | Specific subcode coverage (empty_slice, all_nan, ssh_auth_needed) | Need targeted fixtures | partial (subcodes covered by pytest) |
| §20.11, 20.12 | cartopy_missing, internal_render_error | Need broken environment | n/a |
| §20.13 | Warnings (not errors) | Mostly covered inline by other tests | partial |

## Methodology

Harness: `/tmp/tester_pass_v3.py`. Single Python file that
imports each MCP tool function and invokes it directly. Each
case returns a `(ok, evidence)` dict; the harness tallies pass
/ fail at the end. Real-data cases run against the bundled
`data/omega/` (20 files) and `data/e3sm/` (10 files); synthetic
cases use a 4-D fixture built inline.

The harness deliberately does not exercise the plot-renderer
(rendering PNGs requires a visual oracle); the 1169-test
pytest suite covers that surface already.

## Comparison to v2 (post-cycle-10)

| Metric | v2 (2026-05-12) | v3 (2026-05-12, post-cycle-12) |
|---|---|---|
| Total runnable | 31 | 47 |
| Pass | 31 | 47 |
| Fail | 0 | 0 |
| New since v2 | n/a | 16 (cycle-11 time-series/profile + cycle-12 ncks-parity + e3sm detect re-verify) |
| Findings | 7 (all closed by cycle-10) | 3 (all tester-guide doc bugs, fixed in same PR) |

## What to fix next

Nothing critical. The interactive surface (§1, §15-19) should
get exercised inside a real Claude Code session — that's
fundamentally a different kind of test pass (dogfood-tester
loop, not headless harness).

If a v4 pass is desired:
- Render-side verification (§6–§11 PNG output checks)
- §15 style-by-reference flow with a reference image
- §16 SSH path resolution against a real host
- §17 skill-refiner Stop-hook trigger in Claude Code

These are not blockers for cycle-12 ship.

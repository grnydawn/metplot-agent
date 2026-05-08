# metplot dogfood tester's guide

Evergreen guide for running dogfood test sessions against a built
metplot target. Currently used for cycle 6 (Phase A); reusable for any
future dogfood pass.

## What dogfooding is for

Dogfooding stress-tests the *built plugin payload* against real NetCDF
files and real plot requests. It surfaces what unit tests cannot:
variable-name confusion against your own datasets, regions you care
about that aren't in `regions.md`, color preferences that fight the
defaults, plots that look correct but aren't, plots that fail silently.

Each finding maps to one of six refiner categories. Findings drive
either (a) an immediate spec adjustment for the cycle currently being
planned, or (b) a future refinement draft once the closed-loop layer
is shipping.

**This guide assumes Claude Code as the dogfood target.** Other hosts
follow the same structure; substitute the host's plugin install path
and slash-command syntax where noted.

## Prerequisites

- Python ≥ 3.10.
- Claude Code installed and working.
- At least one NetCDF file you actually care about. (See §"Test data"
  if you need to source one.)
- Working git checkout of `metplot-agent` at the cycle whose build you
  intend to test.

## Installation

### 1. Build the plugin

From the repo root:

```bash
python -m tools.build claude-code
```

This produces `build/claude-code/metplot/`. Inspect the contents to
confirm the build succeeded:

```bash
ls build/claude-code/metplot/
# expect: .claude-plugin/  .mcp.json  README.md  commands/  hooks/
#         mcp-servers/  setup.ps1  setup.sh  skills/
```

### 2. Install into Claude Code's plugin directory

```bash
cp -r build/claude-code/metplot ~/.claude/plugins/
```

If `~/.claude/plugins/metplot/` already exists from a previous
install, remove it first or merge intentionally:

```bash
rm -rf ~/.claude/plugins/metplot
cp -r build/claude-code/metplot ~/.claude/plugins/
```

### 3. Run the bundled installer

```bash
~/.claude/plugins/metplot/setup.sh
```

This installs the MCP servers (`netcdf-reader`, `plot-renderer`) and
their Python dependencies (xarray, matplotlib, cartopy). The script is
idempotent — safe to re-run after a rebuild. Pass `--no-cartopy` or
`--no-scipy` to opt out of optional packages.

The cycle-5 SessionStart hook auto-fires `setup.sh --quiet` on each
new Claude Code session, so manual invocation is only needed for the
first install or after a `tools.build` rebuild changes the bundled
MCP server source.

### 4. Restart Claude Code

Restart so it picks up the new plugin manifest, MCP server
registration, and any hooks. Verify load by typing `/` in the prompt
and checking that `/metplot:setup` and `/refine` (or `/metplot:refine`
on cycle 6+) appear in the slash command list.

### 5. Sanity check

In a new Claude Code session, run:

```
> /metplot:setup
```

Expected: setup script reports "all dependencies present" or installs
what's missing.

Then:

```
> List available metplot skills
```

Expected: agent enumerates `netcdf-inspect`, `netcdf-plot-router`,
`netcdf-plot-map`, `netcdf-plot-timeseries`, `netcdf-plot-profile`.
On cycle 6+, also `skill-refiner`.

If any of these steps fail, log it as a `failure_mode` finding and
stop the install attempt — the dogfood session can't begin until the
sanity check passes.

## Test data

### What makes a good test file

The plugin is designed against four common NetCDF flavors. A useful
dogfood pass exercises at least two of them:

| Flavor | Distinguishing traits | Example sources |
|---|---|---|
| **CMIP6** | Variable names like `tos`, `tas`, `pr`, `psl`, `zg`. Curvilinear ocean grids common. Time in days-since-reference. | ESGF, Pangeo data catalog. |
| **ERA5 reanalysis** | Variable names like `t2m`, `tp`, `msl`, `u10`, `v10`. Regular lat/lon. Time often hourly. | Copernicus CDS. |
| **WRF model output** | Variable names like `T2`, `RAINNC`, `U10`, `V10`, `QVAPOR`. Lambert conformal projection common. Time as character string. | Real WRF runs; the test fixture under `tests/mcp/netcdf_reader/fixtures/` is a small sample. |
| **NOAA OISST / similar gridded products** | Variable names like `sst`, `analysed_sst`. Daily files. Sometimes 0–360 longitude. | NOAA NCEI portal. |

### If you need to generate one quickly

```python
import numpy as np
import xarray as xr

lat = np.linspace(-90, 90, 73)   # 2.5° grid
lon = np.linspace(-180, 177.5, 144)
time = xr.cftime_range("2024-01-01", periods=12, freq="MS")
data = 15 + 10 * np.cos(np.deg2rad(lat[None, :, None])) \
       + np.random.randn(12, 73, 144)

ds = xr.Dataset(
    {"tas": (("time", "lat", "lon"), data,
             {"units": "degC", "long_name": "near-surface air temperature"})},
    coords={"time": time, "lat": lat, "lon": lon},
)
ds.to_netcdf("synthetic_tas.nc")
```

This gives you a file that exercises map plots, time series, and
basic variable resolution.

### What to avoid

- Files larger than ~500 MB unless you specifically want to test slow
  paths (those become a separate `failure_mode` category — performance
  rather than correctness).
- Files with no time dimension (the time-series skill has nothing to
  exercise).
- Files with non-standard CF conventions unless you're specifically
  testing CF-compliance gaps.

## The six categories

Every finding belongs to one of these. If something doesn't fit any,
that's itself a finding — record it in the "Uncategorized" section
and flag for category-set review.

| Tag | What it means | Triggers refinement to |
|---|---|---|
| `alias` | Plugin used the wrong canonical variable name; user said "no, it's actually X" | `aliases.md` |
| `region` | User named a region not in the list, or the plugin used wrong bounds for a known region | `regions.md` + `regions.json` |
| `pitfall` | Something went wrong; you and the agent figured out *why* | Pitfalls section in active SKILL.md |
| `user_pref` | User overrode a default in a way they're likely to want again ("always use viridis for SST") | SKILL.md or YAML config block |
| `default` | User repeatedly chose the same non-default option without explicit "always" | Quick Reference / config default |
| `failure_mode` | Plot looked wrong even though no error fired; or rendered but was unusable | Verification section in SKILL.md |

### Examples per category

#### `alias`

**Scenario A.** User: "Plot SST in the North Atlantic."
Plugin: searches for `sst`, file actually has `tos` (CMIP6). Either
fails to find the variable, or finds something else and plots wrong.
User correction: "It's `tos`, not `sst`."
Finding: `alias` — file used `tos` for SST.

**Scenario B.** User: "Plot 2-meter temperature over Europe."
Plugin: searches for `t2m`, file has `T2` (WRF).
Finding: `alias` — WRF uses `T2` not `t2m`.

#### `region`

**Scenario A.** User: "Plot SST in the Gulf Stream extension."
Plugin: doesn't recognize "Gulf Stream extension" as a region; either
asks for bounds or plots the entire North Atlantic.
Finding: `region` — "Gulf Stream extension" not in `regions.md`,
proposed bounds: `[-75, -45, 35, 45]`.

**Scenario B.** User: "Plot precipitation over the Sahel."
Plugin: maps "Sahel" to `[-20, 30, 5, 25]` but you wanted
`[-18, 40, 12, 18]`.
Finding: `region` — Sahel bounds in `regions.md` too generous;
proposed correction.

#### `pitfall`

**Scenario.** Plot of MSLP in WRF output renders blank. After
inspection: WRF uses 0–360 longitude, but the user named "North
Atlantic" which has negative bounds. The slice was empty.
Finding: `pitfall` — WRF longitude convention vs. region bounds with
negative longitudes. (Maps to the `netcdf-plot-map` SKILL.md
Pitfalls section.)

#### `user_pref`

**Scenario.** User says: "I always want viridis for temperature, not
RdYlBu_r." Said explicitly with "always."
Finding: `user_pref` — confirmed default colormap preference for
temperature variables.

#### `default`

**Scenario.** User has plotted SST four times, each time replied
"actually make the colorbar log scale" without saying "always."
Finding: `default` — user repeatedly chose log-scale colorbar for SST,
no explicit "always." Confidence: medium.

#### `failure_mode`

**Scenario.** Time-series plot of tropical Pacific SST renders
successfully but the values are obviously wrong (10× too large). User
investigates: variable was `tos` in K, plotted as if °C, no unit
conversion warning fired.
Finding: `failure_mode` — silent unit mismatch in time-series skill;
no Verification check on units.

## Suggested test scenarios

Run as many of these as time allows. Each maps to skill coverage and
is sized to reveal at least one finding category.

### Scenario 1 — First-look variable resolution (exercises `netcdf-inspect` + alias)

Pick a file you know contains air temperature, but use a casual name
in the prompt:

> "What's in this file?" — then —
> "Plot the 2-meter air temperature for January 2024."

Watch whether the plugin correctly finds the temperature variable.
Note any aliases the file uses that aren't in `aliases.md`.

### Scenario 2 — Named region map (exercises `netcdf-plot-map` + region)

> "Make a map of [variable] over [common region: CONUS, Europe,
> North Atlantic, Niño 3.4]."

Watch whether the region bounds match what you expect. Try a region
*not* in `regions.md` — e.g. "the Gulf Stream extension," "Tornado
Alley," "the Antarctic Peninsula." Note how the plugin handles
unknown regions.

### Scenario 3 — Multi-variable correction loop (exercises `pitfall`)

> "Plot zonal wind anomalies at 850 hPa for last winter."

This forces several decisions: variable resolution (`ua` vs `u` vs `U`),
vertical level selection, anomaly definition, time window. Each
decision is a chance for the plugin to ask vs. assume. Note where
assumptions surprised you.

### Scenario 4 — Profile / cross-section (exercises `netcdf-plot-profile`)

> "Show me a vertical profile of temperature at 30°N, 45°W on
> 2024-07-15 12 UTC."

Forces the plugin to handle vertical-coordinate detection (pressure
levels vs. model levels vs. height), single-point selection, and
plot styling. Common pitfalls: pressure axis direction (surface at
bottom vs top), units (Pa vs hPa).

### Scenario 5 — Color and styling preferences (exercises `user_pref`)

Run a series of plots, give explicit color feedback:

> "That's good but use viridis instead." — then —
> "For temperature plots in general, prefer viridis going forward."

Note whether the plugin acknowledges the "going forward" signal as a
preference vs. a one-off override.

### Scenario 6 — Failure-mode probe (exercises `failure_mode`)

> "Plot daily-mean precipitation over the Mediterranean for July 2024."

Then *check the resulting plot independently* (e.g. compute the
spatial mean yourself in xarray). Does the plot's range match your
independent calculation? Common silent failures: unit mismatches
(kg/m²/s vs mm/day), accumulation handling (instantaneous vs total),
calendar issues (noleap vs proleptic_gregorian).

### Scenario 7 — Refiner loop probe (cycle-6+ only)

After running scenarios 1–6, end the session. The Stop hook should
fire skill-refiner. Check `.metplot/refinements/` — are there draft
files? Do they match the corrections you made? Any false positives,
missed observations, or wrong category assignments?

This scenario *is* the validation of the closed-loop layer once it
ships. Findings here go into the `failure_mode` category for the
refiner skill itself.

## Findings template

Drop your findings into the cycle's findings doc — for cycle 6, that's
`docs/research/2026-05-08-cycle-6-dogfood-findings.md`. Format:

```markdown
# Cycle 6 dogfood findings

Sessions: [count]   Time invested: [total minutes]
Files exercised: [list of NetCDF files / dataset descriptions]

## alias

### [short title — e.g. "WRF uses T2 for 2m temp"]
- **Date:** 2026-05-08
- **Plot request:** "Plot 2-meter temperature over Europe"
- **Plugin behavior:** Couldn't find `t2m`, asked which variable to use.
- **Correction:** "It's `T2`."
- **Confidence:** high (file is WRF; this is universal for WRF)
- **Should the loop have remembered:** yes — proposed `add_alias` row
  for "T2 → 2m temperature in WRF output."

(repeat per finding under the relevant category)

## region

(repeat structure)

## pitfall

(repeat)

## user_pref

(repeat)

## default

(repeat)

## failure_mode

(repeat)

## Uncategorized

Any finding that didn't fit one of the six categories. Each entry here
is also a finding *about* the category set itself — flag for review.
```

## Example filled report (one entry per category)

```markdown
# Cycle 6 dogfood findings

Sessions: 1   Time invested: 75 minutes
Files exercised:
- ERA5 monthly mean t2m / tp / msl, 2020–2024 (Europe subset)
- CMIP6 historical SST (NorESM2-LM, tos)
- WRF simulation output, 2024-07-15 (Mediterranean)

## alias

### CMIP6 SST is `tos` not `sst`
- **Date:** 2026-05-08T18:42Z
- **Plot request:** "Plot SST anomaly for the North Atlantic in 2023."
- **Plugin behavior:** Searched for `sst` and `analysed_sst`; neither
  in the file. Asked: "I see `tos`. Is that what you mean?"
- **Correction:** "Yes, that's it."
- **Confidence:** high
- **Should the loop have remembered:** yes — `add_alias` for
  "SST → tos in CMIP6 ocean output." Existing aliases.md lists `tos`
  for CMIP but the plugin's variable lookup didn't fall through to
  the table on first try.

## region

### "Gulf Stream extension" not in regions list
- **Date:** 2026-05-08T19:01Z
- **Plot request:** "Plot SST gradient in the Gulf Stream extension."
- **Plugin behavior:** Asked for bounds; I gave `[-75, -45, 35, 45]`.
- **Confidence:** medium (commonly-named feature, but exact bounds
  vary in the literature)
- **Should the loop have remembered:** yes — `add_region` for
  "Gulf Stream extension" with the bounds I gave.

## pitfall

### WRF longitude is 0–360 but region has negative bounds
- **Date:** 2026-05-08T19:18Z
- **Plot request:** "Plot WRF MSLP over the North Atlantic."
- **Plugin behavior:** Rendered a blank map. No error, just empty.
- **Diagnosis:** WRF file uses 0–360 longitude convention; "North
  Atlantic" bounds in regions.md are -80 to 0. Slice returned empty.
- **Confidence:** high
- **Should the loop have remembered:** yes — pitfall in
  `netcdf-plot-map` SKILL.md. Plot-renderer should detect 0–360 grids
  and shift region bounds before subsetting.

## user_pref

### Always viridis for temperature
- **Date:** 2026-05-08T19:30Z
- **User statement:** "Use viridis for temperature plots from now on,
  not RdYlBu_r."
- **Confidence:** high (explicit "from now on")
- **Should the loop have remembered:** yes — `set_config_default`
  for `metadata.config.cmap.temperature = "viridis"` in
  `netcdf-plot-map/SKILL.md`.

## default

### Repeatedly chose log scale for precipitation
- **Date:** 2026-05-08T19:45Z
- **Plot requests:** Three precip plots in a row, each followed by
  "make the colorbar log scale." No explicit "always."
- **Confidence:** medium (pattern observed once in one session)
- **Should the loop have remembered:** maybe — propose
  `set_config_default` with confidence: medium so the human reviewer
  can decide.

## failure_mode

### Silent unit mismatch on tas time-series
- **Date:** 2026-05-08T20:00Z
- **Plot request:** "Time series of monthly mean tas over CONUS, 2020–2024."
- **Plugin behavior:** Rendered with values 270–310 (Kelvin) but the
  axis label said "°C." No unit warning.
- **Diagnosis:** File `units` attribute was "K"; plugin used the
  attribute for axis label but didn't convert.
- **Confidence:** high
- **Should the loop have remembered:** yes — Verification entry in
  `netcdf-plot-timeseries` SKILL.md: detect K vs °C and either
  convert or surface the unit explicitly.

## Uncategorized

(none this session)
```

## When to stop

Stop when:

- The categories you're hitting are repeating with no new variants
  (e.g. you've found three aliases but they're all "WRF uses different
  capitalization" — diminishing returns).
- You've covered the file flavors you care about (CMIP6, ERA5, WRF,
  OISST, etc.).
- You're tired and the next session would produce low-quality notes
  rather than fresh findings.

The cycle-6 spec uses a user-driven stop trigger — there's no fixed
session count, time budget, or coverage threshold. Stop when you say
"enough."

## What to skip

- Don't try to break the plugin with adversarial inputs (corrupted
  NetCDF, zero-byte files, etc.) unless you're specifically auditing
  error handling. Dogfood is about real-use friction, not fuzzing.
- Don't note matplotlib styling preferences that are easily set via
  rcParams — those aren't loop-level concerns.
- Don't propose new skills as findings. The refiner only edits
  existing skills; new-skill proposals belong in a different doc
  (`docs/specs/` for the cycle that adds them).
- Don't refine the refiner. `skill-refiner/SKILL.md` is procedurally
  off-limits to the refinement loop.

## After dogfooding

Hand the filled findings doc back to whoever's coordinating the
cycle. For cycle 6, that means returning to the brainstorm/spec
conversation and saying "here are the findings, ready to reshape the
spec." The cycle-6 spec gets rewritten if findings invalidate the
strawman, then Phase B implementation begins.

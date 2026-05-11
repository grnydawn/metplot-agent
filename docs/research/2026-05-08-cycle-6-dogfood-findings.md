# Cycle 6 dogfood findings

> Phase A of cycle 6 (see `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md`).
> Format and category definitions: `docs/dogfood-tester-guide.md`.

Sessions: 3   Time invested: 50 min
Files exercised:
- `.scratch/synthetic_tas.nc` (synthetic monthly-mean tas, 2024, 73×144 grid, CF-1.7) — sanity check (c) only
- `ocn.hist.0001-02-01_00.00.00.nc` (MPAS-Ocean / Omega `IOStreamsTest` fixture; 7153 cells × 60 vertical layers; unstructured Voronoi; TEOS-10 conservative-temperature + absolute-salinity vocabulary; convention CF low-confidence)
- `cice.nc` (CICE5/6 restart file; 235160 cells, flattened to `ni=235160, nj=1`; 31 variables, all `units=null long_name=null standard_name=null`; convention `unknown` confidence 1.0; no `Conventions` attribute)
- `eamxx.nc` (E3SM EAMxx / SCREAM v1.0.0 atmospheric **restart**; `product: model-restart`; dual-grid — physics `ncol=39620` and spectral-element `elem × gp × gp = 9905 × 4 × 4`; 72 model levels; declares `Conventions: CF-1.8` but most `standard_name` and `long_name` are the literal string `"MISSING"`)

## alias

### CICE sea-ice vocabulary not in alias table
- **Date:** 2026-05-11
- **Files:** `cice.nc`
- **Plugin behavior:** Inspect returned 31 variables, all with `long_name = null`, `standard_name = null`, `units = null`. The agent has no semantic anchor — only the bare CICE variable names — to map a casual user phrase onto.
- **Expected user phrasing → variable:**
  - "ice concentration" / "ice area fraction" → `aicen` (per-category)
  - "ice thickness" / "ice volume" → `vicen`
  - "snow on ice" / "snow volume" → `vsnon`
  - "ice surface temperature" → `Tsfcn`
  - "ice velocity" → `uvel` / `vvel`
  - "melt-pond area" / "melt-pond depth" → `apondn` / `hpondn`
  - "internal ice stress" → `stressp_*` / `stressm_*` / `stress12_*`
  - "ice mask" → `iceumask`
- **Confidence:** high (CICE5/6 conventions are stable across the modeling community).
- **Should the loop have remembered:** yes — `add_alias` entries for the CICE namespace. The `aliases.md` table needs a CICE section.

### EAMxx / SCREAM atmospheric vocabulary not in alias table
- **Date:** 2026-05-11
- **Files:** `eamxx.nc`
- **Plugin behavior:** A subset of variables have real CF `standard_name`s (`T_mid → air_temperature`, `qv → humidity_mixing_ratio`, `qc → cloud_liquid_water_mixing_ratio`, `qi → cloud_ice_mixing_ratio`, `nc → number_concentration_of_cloud_liquid_water_particles_in_air`, `cldfrac_liq`, `precip_liq_surf_mass → atmosphere_mass_content_of_liquid_precipitation`, `ps`, `phis`). The rest carry the literal placeholder string `"MISSING"`. Even the variables with valid `standard_name`s use EAMxx-specific bare names that casual user phrasing won't hit.
- **Expected user phrasing → variable:**
  - "temperature" / "T" / "air temperature" → `T_mid`
  - "surface pressure" / "Psfc" → `ps`
  - "specific humidity" / "water vapor" → `qv`
  - "cloud water" / "liquid cloud" → `qc`
  - "cloud ice" / "frozen cloud" → `qi`
  - "rain" / "rainwater" → `qr`
  - "ozone" / "O3" → `o3_volume_mix_ratio`
  - "TKE" / "turbulence" → `tke`
  - "precipitation" / "precip" → `precip_liq_surf_mass` + `precip_ice_surf_mass` (sum)
- **Confidence:** high for the canonical EAMxx names; the alias mapping is stable per the model's variable registry.
- **Should the loop have remembered:** yes — `add_alias` entries. Where the file provides a valid CF `standard_name`, the alias resolver should match on that first; fall back to `add_alias` rules for the rest.

### TEOS-10 ocean vocabulary
- **Date:** 2026-05-11
- **Files:** `ocn.hist.0001-02-01_00.00.00.nc`
- **Plugin behavior:** MPAS-Ocean uses TEOS-10 standard names rather than the older "potential temperature" / "practical salinity" terminology:
  - `Temperature` has `standard_name = sea_water_conservative_temperature`, units `degree_C`.
  - `Salinity` has `standard_name = sea_water_absolute_salinity`, units `g kg-1`.
- **Expected user phrasing → variable:** "SST" / "sea surface temperature" / "ocean temperature" / "T" → `Temperature` (with implicit surface = `NVertLayers=0`). "salinity" / "S" → `Salinity` (surface-only or 3-D depending on context).
- **Confidence:** high (TEOS-10 is the IOC/SCOR/IAPSO 2010 standard, used by all modern ocean models).
- **Should the loop have remembered:** yes — `add_alias` for TEOS-10 standard names; also a `set_config_default` rule mapping casual "surface X" → the top vertical layer when the file has a `NVertLayers`-style depth axis.

## region

(no findings yet)

## pitfall

### Restart files silently accepted as plot input
- **Date:** 2026-05-11
- **Files:** `cice.nc`, `eamxx.nc`
- **Plugin behavior:** The inspect tool returned a result envelope with `ok: true` for both files even though they are model **restart** files, not analysis history files. Restart files are designed for resuming a run — they lack CF metadata (CICE) or carry placeholder `MISSING` strings instead of real names (EAMxx), and often have flattened or block-decomposed spatial layouts. The user-facing summary did not flag this distinction.
- **Signals available in the file:**
  - `eamxx.nc` carries an explicit `product: model-restart` global attribute.
  - `cice.nc` has no metadata at all (no `Conventions`, no `long_name`s, no `standard_name`s, no `units`) and a flattened layout `nj=1, ni=235160` — strong heuristic restart-shape signal.
- **Plotting impact:** A request like "plot ice concentration" against `cice.nc` would fail at the spatial-coordinates step. With current cycle-3 behavior the user gets a generic "no spatial coordinates" error, not a "this is a restart file — try the matching history file" hint.
- **Confidence:** high. The `product` attr is canonical in E3SM-family output; the shape heuristic is reliable for CICE/MPAS restart layouts.
- **Should the loop have remembered:** yes — add a Pitfall entry in `netcdf-inspect/SKILL.md` for restart detection (read `product` attr; fall back to "no metadata + flattened/no-spatial shape" heuristic) and steer the user to the matching history file.

### MPAS `SshCell` carries a spurious vertical axis
- **Date:** 2026-05-11
- **Files:** `ocn.hist.0001-02-01_00.00.00.nc`
- **Plugin behavior:** `SshCell` (sea surface height at cell center) has shape `[time, NCells, NVertLayers]` = `[1, 7153, 60]`. SSH is inherently 2-D — one value per cell — but this file pads it with a vertical axis. Likely an artifact of the `IOStreamsTest` fixture giving every variable the same shape, but may also occur in real MPAS-Ocean output.
- **Plotting impact:** A naive map-plot would treat `SshCell` as 3-D and either error out or pick an arbitrary vertical level. A semantically-aware skill would notice `standard_name = sea_surface_height` implies 2-D and select the top layer (or warn).
- **Confidence:** medium. Reproduced on a test fixture; need to check whether real MPAS-Ocean history output also does this or whether it's specific to `IOStreamsTest`.
- **Should the loop have remembered:** yes — Pitfall in `netcdf-plot-map`: when a variable's `standard_name` declares a 2-D quantity (e.g. `sea_surface_height`, `surface_air_pressure`, `surface_temperature`) but the file gives it a vertical axis, squeeze the vertical or warn.

### Dual-grid files (E3SM split dycore / physics)
- **Date:** 2026-05-11
- **Files:** `eamxx.nc`
- **Plugin behavior:** The file contains two unrelated spatial grids in parallel: physics columns `ncol=39620` (used by `T_mid`, `qv`, `ps`, etc.) and spectral-element dycore `elem × gp × gp = 9905 × 4 × 4` (used by `*_dyn` variables: `v_dyn`, `vtheta_dp_dyn`, `dp3d_dyn`, `Qdp_dyn`, `phi_int_dyn`, `ps_dyn`). A user request like "plot the temperature field" could map to `T_mid` (physics) or to some dycore variable, and these live on different meshes.
- **Plotting impact:** The agent needs a default-grid rule. Right now there is no scaffolding to detect dual-grid layout or steer the user toward the physics grid for diagnostic plots.
- **Confidence:** high (this is the canonical EAMxx restart layout; will recur in any SCREAM output).
- **Should the loop have remembered:** yes — Pitfall in `netcdf-inspect/SKILL.md`: detect coexisting `ncol`-shaped and `elem×gp×gp`-shaped variable groups; default user-facing plots to the physics grid; surface the dycore-grid variables under a separate "dynamics state (advanced)" heading.

### Precipitation unit conversion landmine
- **Date:** 2026-05-11
- **Files:** `eamxx.nc`
- **Plugin behavior:** `precip_liq_surf_mass` reports units `kg/(m^2)` — a mass-per-area (i.e. instantaneous accumulated mass, not a rate). User-familiar precipitation units are `mm/day` or `mm/hr`. Plotting `precip_liq_surf_mass` as-is on a map labeled "precipitation" would be off by a unit-conversion factor and a time-integration semantics shift.
- **Confidence:** high. Common pattern across E3SM/CESM atmospheric output (raw flux in SI, user expects derived rate).
- **Should the loop have remembered:** yes — Pitfall in `netcdf-plot-map`/`netcdf-plot-timeseries`: when a variable's units are mass-per-area (`kg/m²`) but the user asks for "precipitation", offer or default-apply a conversion to `mm/day` (dividing by water density 1000 kg/m³ and the time step) and surface the assumption.

## user_pref

(no findings yet)

## default

(no findings yet)

## failure_mode

### Plugin MCP tools never reach the agent's tool surface (structural, not a race)
- **Date:** 2026-05-09
- **Scenario:** Sanity check (c) repeated across two consecutive Claude Code sessions (one fresh-install restart, one warm restart). In each, asked the agent: "Inspect the NetCDF file at `.scratch/synthetic_tas.nc`."
- **Plugin behavior:** The `metplot:netcdf-inspect` skill activated correctly both times. Per the skill, the agent should call `netcdf-reader.inspect(path=...)`. In both sessions the MCP tool was **absent from the agent's tool surface** — `ToolSearch` queries for `netcdf`, `metplot`, `inspect`, `peek`, `read_slice`, `find_variables`, `compute_stats`, `resolve_spec` all returned "No matching deferred tools." The agent could not invoke the tool through the normal MCP channel and had to bypass via direct JSON-RPC handshake to the launcher in both sessions.
- **Diagnosis:** Two facts that don't reconcile via Claude Code's normal MCP integration:
   - `claude mcp list` (CLI) reports both servers ✓ Connected, both sessions, immediately.
   - Direct stdio JSON-RPC to `${plugin}/bin/metplot-netcdf-reader` returns all 8 tools and correct results, both sessions.
   - The agent's deferred-tool list shows `mcp__claude_ai_Gmail__*`, `mcp__claude_ai_Google_Calendar__*`, etc. (user-level MCP servers) — but **no plugin-level MCP tools**.
  Initial hypothesis was a session-start race between the `SessionStart` hook (running `setup.sh`) and agent-tool registration. The second restart falsified that: setup is idempotent and finishes in ~1s when packages are already present, but the agent surface was still empty. So the issue is structural — Claude Code's CLI surface for MCP and the agent's tool surface use different mechanisms, and **plugin-bundled MCP servers reach the CLI side but not the agent side**. User-level MCP servers (claude.ai integrations) reach both.
- **Confidence:** high. Reproduced twice, deterministic, with corroborating evidence (the agent's deferred-tool list visibly contains some MCP tools but none of the plugin's).
- **Should the loop have remembered:** no — this is a Claude Code product issue, not a metplot refinement target. Refiner skills can't fix it.
- **Why this matters for dogfood:** any Phase A scenario asking the agent to plot/inspect/slice will fail with "I don't have access to that tool." The user-facing install flow looks fully successful (`Setup complete. 4/4 succeeded`, `claude mcp list` ✓ Connected, server reachable via JSON-RPC). The agent's view is the one that breaks the use case, and there is no obvious user-side workaround. Phase A on Claude Code is **blocked** until either (a) Claude Code closes the gap between CLI MCP and agent MCP for plugin-bundled servers, or (b) metplot ships an alternative path (e.g. server installed at user-level rather than plugin-level, or skills shell out to the launcher directly instead of going through the MCP-tool surface).
- **Suggested next step:** verify on a second host or fresh user account to rule out any local Claude Code state corruption. If reproducible there, escalate to Claude Code product as an MCP-plugin-integration bug. In parallel, investigate whether registering the same MCP servers via `claude mcp add` (CLI / user-level) in addition to plugin-level makes them appear on the agent surface — that would confirm the user-vs-plugin scope hypothesis and give a workaround.

#### Workaround confirmed (2026-05-09)

Registering the same servers at user scope unblocks the agent surface:

```bash
claude mcp add --scope user metplot-netcdf-reader \
  /home/youngsung/.claude/plugins/cache/metplot-local/metplot/0.1.0/bin/metplot-netcdf-reader
claude mcp add --scope user metplot-plot-renderer \
  /home/youngsung/.claude/plugins/cache/metplot-local/metplot/0.1.0/bin/metplot-plot-renderer
```

Run **before** restarting Claude Code so the new session picks up
the user-scope config at startup; running after needs a second
restart for the agent to see them.

After this, `claude mcp list` shows duplicate entries (both
`plugin:metplot:*` and bare `metplot-*` for each server), all
✓ Connected. Only the user-scope (bare-name) entries reach the
agent's deferred-tool surface as `mcp__metplot-netcdf-reader__*`
and `mcp__metplot-plot-renderer__*`. Confirmed by re-running
sanity check (c) — agent invoked the tools through the normal
channel, no JSON-RPC bypass needed.

The workaround is functional but ugly: two registrations per
server, and a bundled-plugin install path that requires manual
post-install steps to actually be useful from the agent. The
underlying gap (plugin-scope MCP servers not reaching the agent
surface) still belongs upstream with Claude Code; documenting the
workaround in the dogfood guide is a stopgap for Phase A only.

### Unstructured-mesh coverage gap — 3/3 real-world files unplottable
- **Date:** 2026-05-11
- **Scenario:** Phase A inspection round on three real-world Earth-system model files (ocean MPAS, sea ice CICE, atmosphere EAMxx) plus one synthetic CMIP-style file.
- **Plugin behavior:**
  - `ocn.hist.0001-02-01_00.00.00.nc` → `spatial: null`, dims `NCells, NEdges, NVertLayers` (MPAS Voronoi unstructured mesh).
  - `cice.nc` → `spatial: null`, dims `nj=1, ni=235160` (CICE flattened/blocked).
  - `eamxx.nc` → `spatial: null`, dims `ncol=39620` (physics) and `elem × gp × gp = 9905 × 4 × 4` (HOMME/SE spectral element).
  - `.scratch/synthetic_tas.nc` → `spatial.coord_kind: rectilinear`, dims `lat=73, lon=144` (the only plottable one).
- **Diagnosis:** 3/3 real files from the user's working set are unstructured (Voronoi, flattened-blocked, and spectral-element). The cycle-3 plot pipeline only handles `rectilinear` and `curvilinear` lat/lon grids (per `result.spatial.coord_kind`). Every real file hits the "no spatial coordinates" stop in `netcdf-inspect`. The synthetic file passes only because it was constructed with a regular lat/lon grid.
- **Confidence:** high — three independent file types, all unstructured, all rejected at the same gate. The pattern reflects the actual landscape of E3SM/CESM-class model output, which is heavily unstructured.
- **Should the loop have remembered:** no — this is a scope question for the cycle-3 spec, not a refiner-target. Refiner skills can't add unstructured-mesh support. Belongs upstream as: "cycle-3 plotting covers a vanishingly small fraction of the operational fleet; consider Phase B / cycle-4 prioritizing unstructured-mesh rendering (xarray-MPAS, PyVista, ParaView, datashader) before further alias/region refinement."
- **Why this matters:** the install-and-tool-surface path is now clean, but the actual plotting path remains blocked for every file the test user has on hand. Cycle-6's "self-improvement loop" assumes the underlying plot tools work end-to-end on the user's data; that assumption doesn't hold for E3SM-style users.

### `standard_name` and `long_name` populated with placeholder strings ("MISSING")
- **Date:** 2026-05-11
- **Files:** `eamxx.nc`
- **Plugin behavior:** Most EAMxx variables have `long_name = "MISSING"` and `standard_name = "MISSING"` (literal six-character strings, not null/absent). The inspect tool's response preserves these strings verbatim — `variables[i].long_name` and `variables[i].standard_name` are populated with `"MISSING"` rather than normalized to `null`.
- **Impact:** Downstream alias resolution that scans `standard_name` for a match will try to match user phrases against `"MISSING"` and get nothing useful. Worse, an alias rule that key on `standard_name` non-null (rather than non-null-and-non-placeholder) treats these variables as if they had real metadata, which they don't.
- **Confidence:** high. EAMxx specifically does this; some other writers use `"none"`, `"N/A"`, `""`. Common pattern in research output.
- **Should the loop have remembered:** yes — normalize a configurable set of placeholder strings (`MISSING`, `missing`, `none`, `N/A`, `"" `) to `null` in `netcdf-reader.inspect` before they reach the agent. Update `netcdf-inspect/SKILL.md` Pitfalls section.

### Convention detection misses obvious file-type fingerprints
- **Date:** 2026-05-11
- **Files:** `cice.nc` (convention: `unknown`, confidence 1.0), `ocn.hist.0001-02-01_00.00.00.nc` (convention: `CF`, confidence `low`)
- **Plugin behavior:** Convention identification currently relies on (a) the `Conventions` global attribute and (b) presence of `standard_name` attributes on variables. With those signals missing or weak, the inspect tool falls back to `unknown` (CICE case) or barely-positive `CF` (MPAS case). It misses unambiguous variable-name fingerprints:
  - CICE: `aicen, vicen, vsnon, Tsfcn, volpn, apondn, hpondn, eicen, esnon, stressp_*, stressm_*, stress12_*, iceumask` — none of these names occur outside CICE.
  - MPAS-Ocean: dims `NCells, NEdges, NVertLayers` are an exact MPAS unstructured-mesh signature.
  - E3SM-EAMxx: coexisting `ncol` + `elem × gp × gp` dims, plus `case`/`source` attrs `E3SM Atmosphere Model (EAMxx)`.
- **Impact:** Without convention identification, the agent can't load the right convention-specific knowledge (CICE category indexing, MPAS mesh requirements, EAMxx dual-grid handling).
- **Confidence:** high. The fingerprints are stable and exclusive to each model.
- **Should the loop have remembered:** partial — the *detection patterns* belong in `netcdf-reader`'s convention-detection layer (not a refinement target the refiner can produce). The *downstream knowledge* (what each variable means, which grid to default to) belongs in `aliases.md` and skill Pitfalls and IS reachable by `add_alias` / pitfall refinement.

### Convention confidence "high" can co-exist with broken CF compliance
- **Date:** 2026-05-11
- **Files:** `eamxx.nc`
- **Plugin behavior:** `convention.primary = CF`, `confidence = high`, `evidence = ["Conventions attr = 'CF-1.8'"]`. But the actual CF compliance is broken — most variables have `standard_name = "MISSING"`. A confidence-high signal on convention is misleading here.
- **Impact:** Downstream code that gates on `convention.confidence == "high"` will treat this as a well-described CF file and may skip fallback heuristics. The user-facing summary doesn't distinguish "header claims CF" from "actually CF-compliant".
- **Confidence:** medium. Single instance so far; need to check whether this pattern recurs in other model output.
- **Should the loop have remembered:** partial — refinement could update the inspect output's confidence-scoring rules. A quick spot-check (e.g., sample 5–10 variable `standard_name` values against the CF standard-name table) would let the inspect tool downgrade confidence on `Conventions: CF-X.Y`-but-stub-`standard_name` files.

## Uncategorized

(no findings yet)

---

## Sign-off

When dogfooding is complete, fill in below and notify whoever's
coordinating cycle 6.

- **Sessions completed:** _
- **Findings count by category:** alias=_, region=_, pitfall=_, user_pref=_, default=_, failure_mode=_, uncategorized=_
- **New category proposed:** none / _
- **Stop reason:** (e.g. "categories repeating", "covered all file flavors", "out of test data")
- **Phase B applier ops justified:** (subset of: replace_section, add_alias, add_region, set_config_default)

# Cycle 3 — Plot skills bundle

> Design document for cycle 3 of `ncplot-agent`. Wires the 5 plotting
> skills (`netcdf-inspect`, `netcdf-plot-router`, `netcdf-plot-map`,
> `netcdf-plot-timeseries`, `netcdf-plot-profile`) to call cycles 1+2
> MCPs end-to-end, plus the agent-side vision step for `style_template`
> extraction. Builds on cycle 1 (`netcdf-reader` MCP) and cycle 2
> (`plot-renderer` MCP).

**Status:** approved by delegation
**Date:** 2026-05-07
**Branch:** `cycle-3-plot-skills`

---

## 1. Overview

Cycle 3 is a **content cycle**. The deliverables are markdown skills
(SKILL.md files), reference data (JSON + markdown), and validation
tests. No new MCP tools, no Python application code beyond the
validation suite.

### What ships

- **5 SKILL.md files** updated with cycle 1+2 MCP signatures, complete
  decision logic, verification steps, and recording-lessons hooks:
  - `src/skills/netcdf-inspect/SKILL.md`
  - `src/skills/netcdf-plot-router/SKILL.md`
  - `src/skills/netcdf-plot-map/SKILL.md`
  - `src/skills/netcdf-plot-timeseries/SKILL.md`
  - `src/skills/netcdf-plot-profile/SKILL.md`
- **Reference data** — both human-readable (markdown) and
  machine-readable (JSON):
  - `src/skills/netcdf-plot-map/references/regions.json` (NEW)
  - `src/skills/netcdf-plot-map/references/regions.md` (existing; kept in sync)
  - `src/skills/netcdf-plot-map/references/colormaps.json` (NEW)
  - `src/skills/netcdf-inspect/references/aliases.md` (existing; minor refresh)
  - `src/skills/netcdf-inspect/references/conventions.md` (existing; minor refresh)
- **Task-log format** locked (`.ncplot/task-log.jsonl` schema for cycle 6 consumption)
- **Skill-validation test suite** (YAML frontmatter, required sections, cross-references, reference data integrity)
- **Integration test** simulating a typical skill flow against cycle 1+2 MCPs with synthetic data

### What does NOT ship

- **Cross-section and Hovmöller plots.** Cycle 2's renderer doesn't
  support these. `netcdf-plot-profile` is vertical-profile-only in
  cycle 3. Router gracefully informs the user and declines.
- **A Python skill loader.** Skills are declarative markdown. Cycle 4
  builds per-target packagers.
- **The skill-refiner.** That's cycle 6. Cycle 3 only provides the
  task-log hooks the refiner will eventually consume.
- **Vision LLM mocking infrastructure.** The skill instructs the agent
  to use its own vision capability — no separate vision tool ships.
- **Inline tools-listing in SKILL.md.** We do not ship a `tools:` field
  in YAML frontmatter (Anthropic's spec is permissive about this).
  Tool dependencies are documented in skill body prose.

### Primary use case

User says "plot SST in the North Atlantic for September 2024" → agent:
1. Loads `netcdf-inspect` skill, calls `netcdf-reader.inspect(path)`
2. Loads `netcdf-plot-router`, decides "map" from request shape
3. Loads `netcdf-plot-map`, resolves "SST" → `tos` via aliases.md, "North
   Atlantic" → bbox via regions.json
4. Calls `netcdf-reader.read_slice(...)` to get the slice
5. Composes a `plot-renderer.render_map(...)` spec, calls renderer
6. Reports min/mean/max + warnings to user
7. If user provided a reference image: extracts `style_template` via
   the prompt at `docs/style_template_extraction_prompt.md`, applies it

### Non-goals

- Not building a Python execution harness for skills (that's the agent's job).
- Not implementing skill-side fallbacks for cycle 1+2 envelope errors
  (the skills surface errors; they don't paper over them).
- Not introducing skill dependencies on the cycle 1/2 Python packages.

---

## 2. Skill inventory

| Skill | Role | Calls | Output |
|---|---|---|---|
| `netcdf-inspect` | Front-load metadata before any plot | `netcdf-reader.inspect`, `netcdf-reader.find_variables`, `netcdf-reader.find_time` | Summary text + cached inspection JSON |
| `netcdf-plot-router` | NL request → plot type | (no MCP calls; dispatches to plot skills) | Selects which plot skill to invoke |
| `netcdf-plot-map` | 2D lat/lon map | `netcdf-reader.{inspect,resolve_spec,read_slice}`, `plot-renderer.render_map` | PNG/PDF/SVG figure file |
| `netcdf-plot-timeseries` | 1D time series (single point or area mean) | `netcdf-reader.{inspect,resolve_spec,read_slice,compute_stats}`, `plot-renderer.render_timeseries` | Figure file |
| `netcdf-plot-profile` | Vertical profile (single point or area mean) | `netcdf-reader.{inspect,resolve_spec,read_slice}`, `plot-renderer.render_profile` | Figure file |

### `netcdf-inspect`

**When to use:** any NetCDF path appears for the first time in a session,
or user asks "what's in this file".

**Outputs:**
- Variable list with shapes, units, long_name
- Time range + frequency
- Spatial extent (lon/lon range, grid resolution)
- Vertical coord (if present)
- Convention detected (CF / WRF / ROMS / unknown)
- Red-flag list (lon convention, calendar, staggered grids, etc.)

### `netcdf-plot-router`

**When to use:** user wants a plot but didn't specify the type, or the
type is implied but worth confirming.

**Decision tree** (refined for cycle 3):

| Cue                                        | Skill                       |
|--------------------------------------------|-----------------------------|
| "map", "spatial", named region, projection, "show me X over <region>" | `netcdf-plot-map` |
| "time series", "over time", "trend", "evolution of", date range only | `netcdf-plot-timeseries` |
| "vertical", "profile", at single point + multiple levels | `netcdf-plot-profile` |
| "cross-section", "transect" | **deferred** — explain to user that cycle 4+ feature |
| "Hovmöller", "lat-time", "lon-time" | **deferred** |
| Variable shape (lat,lon) at one time, no other cues | `netcdf-plot-map` (default for 2D spatial) |

When ambiguous, ask **one** clarifying question with 2–3 options. Don't
list every variant.

### `netcdf-plot-map`

**When to use:** any 2D lat/lon view at single time + (if applicable) single level.

**Outputs:** PNG/PDF/SVG figure of variable on map projection.

### `netcdf-plot-timeseries`

**When to use:** time on x-axis. Single-point extract, regional average,
or global average.

**Outputs:** PNG/PDF/SVG figure of one or more time series.

### `netcdf-plot-profile`

**When to use:** vertical structure at one location/area. Variable on
one axis, vertical coord on the other.

**Outputs:** PNG/PDF/SVG figure of vertical profile.

---

## 3. Reference data

### 3.1 Aliases (`netcdf-inspect/references/aliases.md`)

Existing file; kept. Format: markdown tables grouped by physical
quantity. Used when user names a quantity informally and we need to
map to actual variable names.

Cycle 3 adds:
- A few WRF-specific entries (Q2, RAINC vs RAINNC, U10/V10 surface winds)
- Section heading consistency
- A "How to use this file from a skill" preamble

The skill-refiner appends new aliases to a marked region between
`<!-- REFINER_INSERT_BELOW -->` and `<!-- REFINER_INSERT_ABOVE -->`.
This contract is established in cycle 3 and consumed in cycle 6.

### 3.2 Conventions (`netcdf-inspect/references/conventions.md`)

Existing file; kept. Cycle 3 adds:
- A pointer to cycle-1's `inspect()` returning normalized convention info
- A "How skills use this" preamble

### 3.3 Regions: `netcdf-plot-map/references/regions.{md,json}`

`regions.md` — existing, kept. Human-readable.

`regions.json` — NEW. Machine-readable companion. Schema:

```json
{
  "schema_version": 1,
  "regions": {
    "North Atlantic": {
      "lon_min": -80, "lon_max": 0,
      "lat_min": 20, "lat_max": 70,
      "category": "ocean_basin",
      "notes": "Standard NA region used in CMIP analyses."
    },
    "Niño 3.4": {
      "lon_min": -170, "lon_max": -120,
      "lat_min": -5, "lat_max": 5,
      "category": "climate_index"
    },
    ...
  },
  "categories": ["ocean_basin", "continental", "climate_index", "tc_basin", "polar"]
}
```

Coordinates use **-180..180** convention. Renderer applies
`lon_convention` shift per cycle-2 spec §7.3 if file uses 0..360.

Both files are kept in sync by a validation test (`test_regions_sync.py`).

### 3.4 Colormaps: `netcdf-plot-map/references/colormaps.json`

NEW. Field-character → matplotlib cmap mapping. Used by
`netcdf-plot-map` when user doesn't specify a colormap.

```json
{
  "schema_version": 1,
  "by_field_character": {
    "anomaly":              {"cmap": "RdBu_r", "kind": "diverging", "vcenter": 0.0},
    "departure":            {"cmap": "RdBu_r", "kind": "diverging", "vcenter": 0.0},
    "change":               {"cmap": "RdBu_r", "kind": "diverging", "vcenter": 0.0},
    "temperature_absolute": {"cmap": "RdYlBu_r", "kind": "sequential"},
    "temperature_anomaly":  {"cmap": "RdBu_r",   "kind": "diverging", "vcenter": 0.0},
    "precipitation":        {"cmap": "Blues",   "kind": "sequential"},
    "wind_speed":           {"cmap": "viridis", "kind": "sequential"},
    "pressure":             {"cmap": "viridis", "kind": "sequential"},
    "humidity":             {"cmap": "BrBG",    "kind": "diverging"},
    "geopotential":         {"cmap": "viridis", "kind": "sequential"}
  },
  "default": {"cmap": "viridis", "kind": "sequential"},
  "diverging_default": {"cmap": "RdBu_r", "kind": "diverging", "vcenter": 0.0}
}
```

Skill consults this dict after detecting field character from variable
name + units + `long_name`. Detection rules (in `netcdf-plot-map/SKILL.md`):

- Variable name or `long_name` contains "anomaly" / "departure" / "change" /
  "diff" / "minus" → use `anomaly` entry
- Units in {K, °C, degC} and no anomaly cue → `temperature_absolute`
- Units contain `kg m-2 s-1` or variable name in {pr, tp, RAINNC, precip} →
  `precipitation`
- Units contain `m s-1` and name in {ua, va, u10, v10, U, V, WSPD} →
  `wind_speed`
- Units in {Pa, hPa} and no other cue → `pressure`
- No match → `default`

User's explicit `colormap=...` always wins.

---

## 4. Skill content contract

### 4.1 YAML frontmatter

Every SKILL.md begins with:

```yaml
---
name: <skill-name>
description: <one-sentence trigger description>
---
```

`name` matches the directory name (kebab-case). `description` is a
single sentence (≤ 280 chars) — Anthropic's loader uses this to decide
when to surface the skill.

Cycle 3 does **not** ship a `tools:` field. Tool dependencies are
documented in the body. (Reason: keeps skills portable across hosts;
Claude Code, Desktop, Hermes have different conventions for declaring
tool deps.)

### 4.2 Required body sections

Every SKILL.md must contain (in this order):

1. `# <skill-name>` — title
2. `## When to use` — trigger phrases / contexts
3. `## Quick reference` — numbered procedure (the canonical happy path)
4. (Optional but recommended) `## Pitfalls` — common failure modes
5. `## Verification` — how to confirm output is sensible before reporting success
6. `## Recording lessons` — what to log to `.ncplot/task-log.jsonl` on user corrections
7. `## See also` — sibling skills + reference docs

`netcdf-plot-router` is exempt from `Verification` and `Recording lessons`
since it doesn't produce output directly.

The validation test `test_skill_sections.py` enforces this contract.

### 4.3 MCP tool references

Skills reference MCP tools by their canonical name:
- `netcdf-reader.inspect`
- `netcdf-reader.resolve_spec`
- `netcdf-reader.read_slice`
- `netcdf-reader.compute_stats`
- `netcdf-reader.peek`
- `netcdf-reader.find_variables`
- `netcdf-reader.find_time`
- `netcdf-reader.regrid_to_centers`
- `plot-renderer.render_map`
- `plot-renderer.render_timeseries`
- `plot-renderer.render_profile`

The validation test `test_skill_tool_refs.py` parses each SKILL.md and
asserts every `<server>.<tool>` reference points to a real tool from
the cycle 1/2 dispatch lists.

### 4.4 Cross-references

Skills reference sibling skills and reference data files. The
validation test `test_skill_cross_refs.py` checks:
- `netcdf-inspect` → must exist
- `netcdf-plot-router` → must exist
- `references/aliases.md` → file exists
- `references/regions.{md,json}` → both exist
- `references/conventions.md` → exists
- `references/colormaps.json` → exists

Broken cross-references fail the test with file:line of the broken link.

---

## 5. Style-by-reference flow

Per cycle 2 §8, the `plot-renderer` MCP accepts a `style_template`
field that is deterministically applied. Cycle 3 wires the *agent-side*
vision step.

### 5.1 The flow (encoded in each plot skill)

```
1. Skill detects: did the user provide a reference plot image?
   - "make it look like this <image>"
   - User attached an image to the conversation
   - Path/URL to a saved image referenced in the request

2. If YES:
   a. Skill loads the prompt template from
      `docs/style_template_extraction_prompt.md`.
   b. Skill instructs the agent to call its own vision capability:
      "Apply the prompt template to <image>; return the resulting JSON."
   c. The agent (host LLM with vision) extracts a style_template JSON.
   d. Skill validates the JSON loosely (must be a dict; unknown fields
      are accepted — the renderer ignores them per cycle 2 §8.4).
   e. Skill passes the JSON as `style_template` in the render call.

3. If NO: render normally (no style_template; renderer uses library
   defaults + skill-supplied scientific defaults).
```

### 5.2 What ships in cycle 3

- Each plot SKILL.md has a `## Style by reference` section that:
  - Describes when to detect a reference image
  - Points to the extraction prompt doc
  - Shows an example JSON the vision step should produce
  - Notes the precedence rule (explicit spec field > template > library default)
- A test that asserts each plot skill body contains the section and references the prompt doc

### 5.3 What does NOT ship in cycle 3

- A Python helper that wraps the vision call. The agent owns vision;
  the skill is just instruction.
- A reference-image library or curated style examples (future).
- Automatic image-classification (e.g., "this is a Robinson map"). The
  prompt doc + the host LLM handle this.

### 5.4 Provenance

The `source` block in `style_template` (per cycle 2 §8.1) flows
untouched to `oracle.style_template_applied.source`. Skills are
expected to populate it with at least:
- `image_path` — the user-provided reference (path or URL)
- `extracted_by` — the host LLM model id (e.g., `claude-opus-4-7`)
- `extracted_at` — ISO timestamp
- `confidence` — host LLM's self-rated confidence

Cycle 6 skill-refiner will use this for audit trails.

---

## 6. Task-log format (`.ncplot/task-log.jsonl`)

Frozen in cycle 3. Cycle 6 (skill-refiner) reads this file and proposes
patches.

### 6.1 Schema

JSON Lines (one JSON object per line). Each event is one of:

**`alias_correction`** — user corrected a variable-name resolution

```json
{
  "ts": "2026-05-07T14:30:00Z",
  "skill": "netcdf-inspect",
  "step": "alias_correction",
  "input": "user said: SST",
  "resolved": "tos",
  "via": "user_correction",
  "context": "CMIP6 historical run"
}
```

**`region_correction`** — user corrected a region bbox

```json
{
  "ts": "2026-05-07T14:35:00Z",
  "skill": "netcdf-plot-map",
  "step": "region_correction",
  "input": "user said: North Atlantic",
  "resolved_initial": {"lon_min": -80, "lon_max": 0, "lat_min": 20, "lat_max": 70},
  "resolved_final":   {"lon_min": -90, "lon_max": 10, "lat_min": 15, "lat_max": 75},
  "via": "user_correction"
}
```

**`colormap_correction`** — user corrected a colormap choice

```json
{
  "ts": "2026-05-07T14:40:00Z",
  "skill": "netcdf-plot-map",
  "step": "colormap_correction",
  "input": "auto-picked: RdYlBu_r",
  "resolved": "viridis",
  "via": "user_correction",
  "context": {"variable": "tos", "units": "K"}
}
```

**`projection_correction`**, **`unit_conversion_skipped`**, **`level_correction`** — analogous shapes.

### 6.2 Required fields

Every event must have:
- `ts` — ISO 8601 UTC timestamp
- `skill` — skill name (matches a SKILL.md frontmatter `name`)
- `step` — event subtype (one of the above or new ones added in future cycles)
- `via` — provenance (`user_correction`, `auto_detected`, `prompt_clarified`)

Optional but recommended: `input`, `resolved`, `context`.

### 6.3 Append discipline

- Skills append a single JSON-line per event (no overwriting)
- File created lazily on first append
- File is gitignored (already covered by `.ncplot/` blanket ignore)
- Cycle 6 reads and rotates this file

### 6.4 Validation

A test (`test_task_log_format.py`) asserts:
- The task-log schema is documented in this spec (so cycle 6 has a contract)
- A small synthetic JSONL example parses cleanly
- Skills' `## Recording lessons` sections describe formats consistent with this schema

No skill will write to the task-log during cycle 3 — that's the agent's
responsibility when executing the skill. Cycle 3 only locks the schema.

---

## 7. Per-skill decision logic

### 7.1 `netcdf-inspect`

```
1. Compute file hash (cycle-1's cache key — already documented in
   netcdf-reader spec). Check .ncplot/inspections/<hash>.json.
2. If cache hit: report from cache, mark "cached" in summary.
3. If miss: call netcdf-reader.inspect(path). Cache via the MCP's own
   cache (the MCP handles writing; skill just consumes).
4. Surface to user (per skill body).
5. If user says variable name doesn't match: log alias_correction.
```

### 7.2 `netcdf-plot-router`

```
1. Has the file been inspected? If not, run netcdf-inspect first.
2. Apply the decision tree (§2 above).
3. If matched cross-section / Hovmöller cue: respond with
   "Cross-section / Hovmöller plots are not yet supported. Currently
   I can do maps, time series, and vertical profiles. Re-phrase or
   wait for a future release."
4. Otherwise: invoke the matched plot skill, forwarding:
   - file path
   - resolved variable name (from inspect step)
   - region/time/level constraints from request
```

### 7.3 `netcdf-plot-map`

Refined from the existing stub. New steps:
- Step 8 (style template): if reference image present, run vision flow.
- Step 9 (composition): build render_map spec including `style_template` if extracted.
- Step 10 (call): `plot-renderer.render_map(spec=...)`.
- Step 11 (verify): check oracle for `nan_fraction < 1.0`, plotted_min/max sane, no critical warnings.
- Step 12 (record): if user corrected anything, append to task-log.

Field-character → colormap detection rules per §3.4.

Region resolution: prefer regions.json (machine-readable lookup); fall
back to asking user for bbox.

Unit conversion (K → °C, Pa → hPa, kg m⁻² s⁻¹ → mm/day) is decided
skill-side via the prompt — but the renderer doesn't do unit conversion.
The skill must supply already-converted values to `read_slice` (which
also doesn't convert) — wait. **Actually:** `read_slice` returns raw
data with original units. Skill-side conversion needs to happen between
`read_slice` and `render_map`. The skill must compute the converted
values numerically.

This is an ambiguity in the cycle-1 spec we should clarify here:
**unit conversion is the skill's responsibility.** The skill gets raw
values from `read_slice`'s `result.values` (inline form), applies the
conversion (e.g., `[v - 273.15 for v in values]`), and passes to
`render_map` with the new units in the title and colorbar_label.

For the file form (slice_ref), the skill cannot easily convert without
loading the file itself. Decision: when unit conversion is needed,
force the inline form by setting a small `region` so that the slice
fits in `max_inline_bytes`, OR don't convert and surface the original
unit. Document this trade-off in the skill body.

### 7.4 `netcdf-plot-timeseries`

Resolves spatial reduction (point / region / global) before reading.
Uses `netcdf-reader.read_slice` with appropriate selectors.

For regional averages, the skill computes area-weighted mean using
`cos(lat)` weighting AFTER `read_slice` returns inline data. (Renderer
doesn't aggregate.)

For global means: same, with full-globe extent.

Time aggregation (monthly, annual, seasonal): documented as a
skill-side computation step.

Pitfalls section now has concrete fixes for each TODO from the stub:
- Area weighting math: `cos(deg2rad(lat))` weighting before mean
- Leap year + noleap calendar: pass through `cftime` → use `.dt.month`
  for grouping; document that "annual mean" with noleap calendar means
  365 days
- Missing data: use `np.nanmean`, report `nan_fraction` from oracle
- Trend lines: pass `trendline="linear"` to renderer; user can override

### 7.5 `netcdf-plot-profile`

Vertical-only in cycle 3. Cross-section and Hovmöller deferred.

Detects pressure vs height vs depth from `vertical_units` attr:
- Pa, hPa → pressure (log y, invert axis)
- m, km → height (linear y, no invert)
- depth (often `depth` coord with `positive="down"`) → linear y, invert (deepest at bottom)

Hands off to `plot-renderer.render_profile` with appropriate flags.

---

## 8. Testing strategy

### 8.1 Layer 1 — content validation tests

`tests/skills/test_skill_frontmatter.py` — every SKILL.md has valid
YAML frontmatter with `name` matching directory and `description` ≤
280 chars.

`tests/skills/test_skill_sections.py` — every SKILL.md has the required
sections (§4.2 above) in the correct order.

`tests/skills/test_skill_tool_refs.py` — every `<server>.<tool>`
reference in skill bodies points to a real tool name from the cycle
1/2 dispatch lists.

`tests/skills/test_skill_cross_refs.py` — every `references/<file>`
mention or sibling-skill mention points to a real file.

`tests/skills/test_skill_style_section.py` — every plot skill (map /
timeseries / profile) has a `## Style by reference` section that
points to `docs/style_template_extraction_prompt.md`.

### 8.2 Layer 2 — reference data integrity tests

`tests/skills/test_regions_sync.py` — every region in `regions.md`'s
tables exists in `regions.json` with matching coordinates, and vice
versa.

`tests/skills/test_regions_schema.py` — `regions.json` parses, has
`schema_version`, all entries have lon/lat keys with sensible numeric
ranges.

`tests/skills/test_colormaps_schema.py` — `colormaps.json` parses, has
`schema_version`, all cmap names in matplotlib's registry, all `kind`
values in {sequential, diverging, categorical}.

`tests/skills/test_aliases_format.py` — `aliases.md` has the
`<!-- REFINER_INSERT_BELOW -->` / `<!-- REFINER_INSERT_ABOVE -->`
markers in the right place; section structure parses.

### 8.3 Layer 3 — task-log format test

`tests/skills/test_task_log_format.py` — synthetic JSONL examples for
each event type (`alias_correction`, `region_correction`, etc.) parse
and contain required fields.

### 8.4 Layer 4 — integration test (skill-flow simulation)

`tests/skills/integration/test_map_flow.py` — simulates the typical
"plot SST in North Atlantic" flow against synthetic data. Steps:

1. Create a small synthetic CF-compliant NetCDF file with `tos`
   variable
2. Call `netcdf-reader.inspect()` — assert convention is CF, variable
   list contains `tos`
3. Look up "North Atlantic" in `regions.json` — assert bbox
4. Call `netcdf-reader.read_slice()` with the bbox + variable
5. Look up colormap for `tos` (units K → temperature_absolute →
   RdYlBu_r) from `colormaps.json`
6. Call `plot-renderer.render_map()` with the resolved spec
7. Assert envelope.ok, file exists, oracle is correct

This is **not** an LLM end-to-end test (no Claude in the loop). It's a
mechanical simulation that proves the skill instructions can be
executed by a competent agent against the actual MCP outputs.

### 8.5 Layer 5 — what we don't test

- The vision step. The host LLM owns vision; we don't mock it.
- The router's NL classification. Skill body has the decision tree;
  the agent applies it.
- Skill loading per host (cycle 4's job).

---

## 9. Open risks

### 9.1 Skill drift across hosts

**Risk:** Anthropic's SKILL.md format and Hermes' agentskills.io format
diverge in future versions; one canonical SKILL.md no longer parses for
both.

**Response:** Keep skills minimal; rely on YAML frontmatter and standard
markdown sections. Cycle 4 (Claude Code target) will validate
host-specific compatibility. Cycle 3 stays format-conservative.

### 9.2 Reference data sync

**Risk:** `regions.md` and `regions.json` go out of sync (manual edits
to one but not the other).

**Response:** `test_regions_sync.py` catches drift. Documented in this
spec that any region edit must update both files.

### 9.3 Unit conversion in skills vs renderer

**Risk:** Skills convert units (K → °C) before passing to renderer, but
slice file form (`slice_ref`) doesn't surface raw values to the skill
— the renderer reads the file directly. So unit conversion must
happen on inline form OR the renderer-side title must say "K (raw)".

**Response (this cycle):** Document the trade-off in
`netcdf-plot-map/SKILL.md`. When user requests a conversion, the skill
forces inline form by sizing the slice; if too big, it uses raw units
and notes the conversion in chat instead.

### 9.4 Cross-section / Hovmöller user expectations

**Risk:** User asks for cross-section, gets the deferral message,
gets frustrated.

**Response:** The router's deferral message is helpful: it explains
what IS supported (map / timeseries / profile) and offers to do a
profile-style adjacent thing if applicable.

### 9.5 Schema-version drift

**Risk:** `regions.json` / `colormaps.json` schema changes in future
cycles, but old cached data uses old schema.

**Response:** `schema_version` field on every JSON. Skills must check
the version and refuse / warn on mismatch. Cycle 3 establishes
`schema_version: 1` for both.

### 9.6 Task-log explosion

**Risk:** A long-running session writes thousands of task-log entries;
cycle 6's refiner must handle them efficiently.

**Response:** Cycle 6's problem (rotation, deduplication). Cycle 3 just
specifies the format and the append discipline.

---

## 10. Cross-cutting principles

### 10.1 Inherited from cycles 1+2

1. **Envelope discipline.** Skills must surface envelope errors and
   warnings to the user verbatim — don't paper over them.
2. **No silent fallback.** If the renderer returns `cartopy_missing`,
   the skill says so and offers to install (cycle 5's auto-installer
   will handle this; for now, the skill says "install cartopy with
   `uv pip install cartopy` and try again").
3. **TDD for the validation tests.** Write the failing test, fix the
   skill content, re-test.

### 10.2 New for cycle 3

4. **Skills are pure instruction.** No skill includes Python code that
   gets executed automatically. The agent reads the skill and acts.
5. **Required body sections (§4.2).** Every SKILL.md has them in order.
6. **Reference data is dual-format.** Human-readable (markdown) +
   machine-readable (JSON) for any data a skill consumes
   programmatically. They stay in sync.
7. **Tool references are canonical.** `<server>.<tool>` — never bare
   tool names that could ambiguate when multiple MCPs are loaded.
8. **Style by reference is documented in every plot skill.** Not a
   separate skill.
9. **Task-log schema is a contract** consumed by cycle 6. Schema
   version pinned at 1 in cycle 3.

### 10.3 What cycle 3 explicitly does not establish

- A skill execution engine. Skills are read by the host LLM and
  followed.
- A skill versioning system. Each skill is on its master branch.
- A skill marketplace / sharing format. Cycle 4+ for that.

---

## End of spec

Implementation plan goes in
`docs/plans/2026-05-07-cycle-3-plot-skills.md`.

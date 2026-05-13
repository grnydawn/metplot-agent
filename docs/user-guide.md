# metplot-agent — User's Guide

A walkthrough of using `metplot-agent` end-to-end. Covers the
mental model, the inspect → slice → render pipeline, plotting
recipes for each supported NetCDF convention, time/region/level
selection, style-by-reference, the refiner loop, and
troubleshooting.

> **Before you start**: install metplot for your host. See `README.md`
> for the install/uninstall steps per host. This guide assumes the
> install succeeded and you can see `/metplot:setup` and
> `/metplot:refine` in your agent's slash-command menu (or the
> host equivalent).

---

## Table of contents

1. [Mental model](#1-mental-model)
2. [The pipeline: inspect → slice → render](#2-the-pipeline-inspect--slice--render)
3. [Plotting recipes by file type](#3-plotting-recipes-by-file-type)
   - [Rectilinear (CMIP, ERA5)](#31-rectilinear-cmip-era5)
   - [WRF (curvilinear + staggered)](#32-wrf-curvilinear--staggered)
   - [ROMS (curvilinear + sigma vertical)](#33-roms-curvilinear--sigma-vertical)
   - [MPAS-Ocean (unstructured + mesh pairing)](#34-mpas-ocean-unstructured--mesh-pairing)
4. [Selecting time, region, and vertical level](#4-selecting-time-region-and-vertical-level)
5. [Time-series and profile plots](#5-time-series-and-profile-plots)
6. [Style by reference (extract style from a screenshot)](#6-style-by-reference-extract-style-from-a-screenshot)
7. [Multi-file globs and time concatenation](#7-multi-file-globs-and-time-concatenation)
8. [The skill-refiner loop](#8-the-skill-refiner-loop)
9. [Slash commands cheat-sheet](#9-slash-commands-cheat-sheet)
10. [Reference data: aliases, regions, colormaps](#10-reference-data-aliases-regions-colormaps)
11. [Troubleshooting](#11-troubleshooting)
12. [Remote file access via metplot-ssh-broker](#12-remote-file-access-via-metplot-ssh-broker)
13. [File-format support matrix](#13-file-format-support-matrix)

---

## 1. Mental model

`metplot-agent` is a thin layer between you and two MCP servers:

- **`netcdf-reader`** (14 tools): `inspect`, `read_slice`,
  `find_variables`, `find_time`, `resolve_spec`, `peek`,
  `compute_stats`, `regrid_to_centers`, `reduce_variable`,
  `dump_cdl`, `find_region`, `slice_along_section`,
  and two more (see `src/mcp/netcdf_reader/server.py`).
- **`plot-renderer`** (4 tools): `render_map`,
  `render_timeseries`, `render_profile`, `render_section`.

For NetCDF files on OTP-protected remote hosts (OLCF /
ALCF / NERSC), there is also **`metplot-ssh-broker`** — a
separate CLI you run in your own terminal that lets the
agent reach `ssh://host/path.nc` URLs without ever seeing
your passcode. See §12.

Five skills (markdown files with YAML frontmatter) guide the agent
on when to call which MCP tool. You don't invoke skills directly
— the agent loads them based on the words in your prompt.

The pipeline:

```
your prompt
   │
   ▼
agent picks a skill (e.g. netcdf-plot-map)
   │
   ▼
agent calls MCP tools (inspect → resolve_spec → read_slice → render_map)
   │
   ▼
MCP servers return structured envelopes; renderer writes a PNG to disk
   │
   ▼
agent reports the PNG path + any warnings to you
```

A few invariants worth knowing:

- **Inspect always runs first** on a new file in a new session.
  The agent caches the result under `.metplot/inspections/` keyed
  on file mtime, so subsequent prompts about the same file are
  fast.
- **The renderer always returns a PNG path.** Even if you didn't
  ask for an output path, the renderer auto-names something
  under `.metplot/plots/`. Use `output_path: "/your/path.png"` in
  your prompt to control it.
- **Every MCP tool returns one of three envelope shapes**:
  `success`, `error`, or `ambiguous`. Ambiguous envelopes carry
  candidate values you can pick from on retry — the agent shows
  them to you and asks.

---

## 2. The pipeline: inspect → slice → render

### Inspect

The first thing the agent does with a new file. Returns:

- `convention.primary` — CF / WRF / ROMS / MPAS / CMIP / unknown
- `variables[]` — list of plottable variables with `name`,
  `units`, `long_name`, `standard_name`, `dims`, `shape`
- `time` — start, end, calendar, n, monotonicity
- `spatial` — `coord_kind: rectilinear | curvilinear |
  unstructured` plus lat/lon names + ranges + convention
- `vertical` — kind (pressure / model_level / sigma / eta / depth /
  height) + range
- `dims` — every dim and its size
- `attrs` — file-level global attributes

Try it:

> **You**: Inspect `/home/me/data/era5_t2m.nc`.
>
> **Agent**: (calls `netcdf-reader.inspect`)
> Found a CF-1.7 file with 2 variables. Highlights:
> - `t2m` — 2-metre temperature, K, dims `(time=8760, lat=181, lon=360)`
> - Time range 2024-01-01..2024-12-31, hourly, monotonic increasing
> - Spatial: rectilinear, lat -90..90, lon 0..359.75 (0..360
>   convention)
> No vertical dim. Ready to plot.

### Slice (usually invisible)

When you ask for a plot, the agent calls `read_slice` internally
to pull just the cells it needs (time index, level, region). The
slice either inlines as JSON (for small grids) or materializes as
a NetCDF file under `.metplot/slices/` (for big ones).

You can also ask for stats directly without plotting:

> **You**: What's the global-mean t2m for July 2024?
>
> **Agent**: (calls `compute_stats`)
> Mean: 288.4 K (15.3 °C), min 215.1 K, max 318.7 K, σ 21.8 K.

### Render

`render_map` (for 2-D), `render_timeseries` (for 1-D), or
`render_profile` (for vertical). All produce PNGs.

---

## 3. Plotting recipes by file type

### 3.1 Rectilinear (CMIP, ERA5)

The default and simplest case. Lat and lon are 1-D, the field is
a 2-D `(lat, lon)` slice after time/level reduction.

> **You**: Map the t2m for 2024-07-15 12:00 UTC.

The agent inspects (or uses the cache), calls
`netcdf-reader.find_time` to map the ISO date to an index,
slices, renders, reports the PNG. Default projection PlateCarree,
default colormap `RdYlBu_r` for temperature.

Override anything:

> **You**: Same but use the Robinson projection, viridis colormap,
> and save to `/tmp/era5.png`.

### 3.2 WRF (curvilinear + staggered)

WRF files have 2-D `XLAT`/`XLONG` coord arrays and U/V variables on
staggered grids (Arakawa C). `metplot-agent` detects WRF via the
`TITLE` global attr, marks staggered variables in inspect, and
calls `netcdf-reader.regrid_to_centers` automatically before
rendering if you ask for a staggered variable.

> **You**: Plot U wind at the lowest model level for the first
> output time in `wrfout_d01.nc`.
>
> **Agent**:
> Detected WRF (cycle 4 supported). `U` lives on `west_east_stag`
> — regridding to centers before rendering. Lowest model level:
> bottom_top=0. Time t=0 = 2024-09-01 00:00:00. (calls render_map)
> Wrote `.metplot/plots/wrf_U_2024-09-01_00.png`.

### 3.3 ROMS (curvilinear + sigma vertical)

ROMS uses `lat_rho`/`lon_rho` for spatial and `s_rho`/`Cs_r` for
the sigma vertical. Detection via `type = "ROMS/TOMS history file"`
attr or the `s_rho` dim.

> **You**: Plot ROMS temperature at the surface for the last time
> step.

The agent selects `s_rho=0` (surface for ROMS sigma convention)
or `s_rho=-1` depending on the file's stretching profile direction,
honors any explicit `level` you supply.

### 3.4 MPAS-Ocean (unstructured + mesh pairing)

The cycle-8 path. MPAS files split geometry (mesh) from data
(history) — you need both to plot.

If you give the agent a history file with no geometry:

> **You**: Inspect `/data/ocn.hist.0001-02-01_00.00.00.nc`.
>
> **Agent**:
> This is an MPAS history file — it ships `Temperature`,
> `Salinity`, etc. but no `latCell`/`lonCell` coords (those live
> in the matching mesh file). Likely sibling mesh files in
> `/data/`: `ocean_mesh.nc`. Want me to retry inspect with
> `mesh_path=ocean_mesh.nc`?

After confirming the mesh:

> **You**: Yes, use that.
>
> **Agent**: (calls `inspect(path, mesh_path=ocean_mesh.nc)`)
> Got the paired envelope. `spatial.coord_kind = unstructured`,
> 7153 cells, lat range [-77, 90], lon range [0, 360] (`0..360`
> convention). Variables: `Temperature` and `Salinity` are tagged
> `cell_centered`; `NormalVelocity` is on the edge dim.
> Ready to plot.

Then plot:

> **You**: Map Temperature at the surface for the first time step.
>
> **Agent**: (slices + renders)
> Wrote `.metplot/plots/mpas_temperature_surface.png`. 7153 cells
> rendered as Voronoi polygons via uxarray; range -1.72..29.82 °C.

Mesh-pairing detail:
- The agent searches the history file's directory for likely
  mesh files via these heuristics, in order: `<base>_mesh.nc`,
  `init.nc`, `*_mesh.nc`, `*mesh*.nc`.
- The first candidate is offered with confidence 0.7; the rest at
  0.5. Pick one explicitly to override.
- Once paired, the `mesh_path` flows through `read_slice` and
  `render_map` automatically.

---

## 4. Selecting time, region, and vertical level

### Time

Informal phrasing works:

| You say | Agent maps to |
|---|---|
| "first" / "earliest" | time index 0 |
| "last" / "latest" / "most recent" | time index -1 |
| "September 2024" | nearest-match in time coord; warns on non-exact |
| "2024-09-15" | exact match if present, nearest otherwise |
| "2024-09-15T12:00:00Z" | exact ISO |
| "around July" | falls through to ambiguous; agent prompts |

The agent uses `netcdf-reader.find_time` for fuzzy lookups. If
the calendar is `360_day` or `noleap`, it normalizes via cftime.

### Region

Named regions (from `references/regions.json`):

- "North Atlantic", "Tropical Pacific", "Arctic", "Antarctic",
  "Mediterranean Sea", "Bay of Bengal", "Southern Ocean", …

Custom bbox:

> "Plot t2m over [40, 0, 60, 30]" → (lat_min, lon_min, lat_max,
> lon_max).

Or named region:

> "Plot t2m over the North Atlantic" → bbox from regions.json.

**Longitude-convention safety**: if the file uses `0..360` and
your region uses negatives (e.g. -80..0 for the Atlantic), the
renderer auto-shifts. You'll get a `LON_SHIFT_APPLIED` warning
in the response.

> Region clipping is **not** supported on unstructured (MPAS)
> meshes yet (cycle 9+). Map plots of unstructured fields are
> always global.

### Vertical level

Numeric:

> "at 500 hPa" → finds the nearest pressure level
> "at 1500 m" → nearest height/altitude level
> "at sigma 0.5" → for ROMS / WRF eta

Sentinels:

> "at the surface" → top-of-atmosphere or surface depending on
> variable; for ocean files defaults to the shallowest layer;
> for WRF eta defaults to `bottom_top=0`; for MPAS-Ocean
> defaults to `NVertLayers=0`.

---

## 5. Time-series and profile plots

### Time-series

> **You**: Plot a time-series of global-mean t2m for 2024.

The agent uses `netcdf-plot-timeseries`, which calls `compute_stats`
to area-weight the mean across the file's spatial dim, then
`render_timeseries` to plot.

> **You**: Plot the t2m time series at lat=40, lon=-74 (New York).

Single-point: agent finds the nearest grid cell, slices, plots.

### Vertical profile

> **You**: Plot the temperature profile at lat=0, lon=180 for
> 2024-09-15.

The agent uses `netcdf-plot-profile`, slices to a single (lat,
lon, time) column, renders the vertical axis on the y-axis (with
pressure inverted so high pressure is at the bottom).

### Cross-section

> **You**: Plot a north-south temperature cross-section along
> lon=0 for 2024-09-15.

`netcdf-plot-profile` handles this too — a 2-D slice with one
spatial dim and one vertical dim.

---

## 6. Style by reference (extract style from a screenshot)

If you have a paper figure or a journal plot you want to mimic,
attach the image and say:

> **You**: Make a map of t2m for September 2024 with the same
> visual style as this. *[attaches screenshot.png]*

The agent reads
`docs/style_template_extraction_prompt.md`, runs its vision
capability on the reference image, and produces a `style_template`
JSON with extracted projection, colormap, vmin/vmax, gridlines,
colorbar position, font scale, aspect, and a confidence score.
That template flows into the render spec, where explicit fields
in your prompt override template fields, which override library
defaults.

The result envelope includes a `style_template_applied` block
recording which fields came from the reference image and which
from your prompt — useful for auditing reproductions of published
figures.

---

## 7. Multi-file globs and time concatenation

CMIP-style output often ships one file per month or per year.
Globs work:

> **You**: Inspect `/data/era5_t2m_2024-*.nc`.

The agent uses `multi_file_combine` to concat along time
automatically. The combined envelope reports `kind:
"local_multi"`, `files: [...]` (sorted), and one continuous time
range.

> Multi-file unstructured time-concat is **not** supported yet
> (cycle 9+). For MPAS-Ocean time series across multiple history
> files, you currently need to load them sequentially.

---

## 8. The skill-refiner loop

When you correct the agent ("no, SST is `tos` in CMIP files, not
`sst`"), the relevant skill writes an entry to
`.metplot/task-log.jsonl`. At the end of the session, the
`skill-refiner` skill reads that log and produces draft
refinement files in `.metplot/refinements/`.

You then review and apply them:

```bash
metplot-refine        # interactive review
metplot-refine --list # show pending drafts
```

Each draft has a YAML frontmatter naming the target file,
section, operation (`add_alias` / `replace_section` /
`set_config_default` / `append`), confidence, and evidence.
Accept, edit, or reject each one. Accepted ones merge into the
canonical `src/skills/` files; the next build distributes them.

On Claude Code, the `Stop` hook auto-fires `/metplot:refine` in
a fresh subagent at session end. On other hosts the loop is
manual — invoke `/refine` (or run the skill manually for Claude
Desktop / Codex) when you want it to produce drafts.

Per cycle-6 Phase B, three applier ops are shipping
(`add_alias`, `replace_section`, `set_config_default`);
`add_region` is stubbed pending region findings in a future
Phase A.

See `docs/self-improvement.md` for the design rationale.

---

## 9. Slash commands cheat-sheet

| Command | Available on | What it does |
|---|---|---|
| `/metplot:setup` | claude-code, gemini-cli, cursor, copilot, antigravity | Install/refresh Python deps (cartopy, scipy, MCP servers) |
| `/metplot:refine` | claude-code, gemini-cli, cursor, copilot, antigravity | Run `skill-refiner` against this session |
| (no slash, manual) | codex, claude-desktop | Invoke `skill-refiner` by name in chat |
| `metplot-refine` (shell) | all hosts | Apply pending refinements interactively |
| `metplot-refine --list` | all hosts | List pending refinement drafts |

> Codex's user-defined slash command authoring format is
> undocumented as of May 2026, so `/refine` doesn't ship for
> Codex. The `skill-refiner` skill is in the bundle and can be
> invoked manually ("run the skill-refiner procedure for this
> session" works).

---

## 10. Reference data: aliases, regions, colormaps

Three reference files ship inside the skill bundles:

- `src/skills/netcdf-inspect/references/aliases.md` — maps user
  phrases to canonical variable names per file type. "SST" → `tos`
  (CMIP) / `sst` (NOAA OISST). The skill-refiner appends to this
  via `add_alias`.
- `src/skills/netcdf-plot-map/references/regions.md` and
  `regions.json` — named-region bounding boxes. Edit the JSON
  to add a region; the renderer's region resolver looks here
  first.
- `src/skills/netcdf-plot-map/references/colormaps.json` —
  field-character → colormap mapping. `temperature_absolute` →
  `RdYlBu_r`, `anomaly` → `RdBu_r`, `precipitation` → `Blues`,
  etc. Add a row to extend.

---

## 11. Troubleshooting

### "I don't see `/metplot:setup` in autocomplete"

The plugin isn't loaded. Per host:
- Claude Code: check `/plugin list` for `metplot`. If missing,
  re-run `/plugin marketplace add` and `/plugin install`.
- Cursor / Copilot / Gemini CLI / Antigravity: restart the agent.
- Claude Desktop: paste `project_instructions.md` into the
  Custom Instructions panel and reload the project.

### "It says cartopy is missing"

Run `/metplot:setup` (or the host equivalent). It installs
cartopy + scipy + the MCP servers via `pip install`. On systems
without PROJ/GEOS C libraries, install those first (`brew install
proj geos` on macOS, `apt install libproj-dev libgeos-dev` on
Debian/Ubuntu).

### "MCP servers show `✓ Connected` but the agent can't see the tools"

Specific to Claude Code, post-install (cycle 6 dogfood
finding). Workaround: register the servers at user-scope in
addition to plugin-scope:

```bash
claude mcp add --scope user metplot-netcdf-reader \
  ~/.claude/plugins/cache/metplot-local/metplot/0.1.0/bin/metplot-netcdf-reader
claude mcp add --scope user metplot-plot-renderer \
  ~/.claude/plugins/cache/metplot-local/metplot/0.1.0/bin/metplot-plot-renderer
```

Then restart Claude Code. See `docs/research/2026-05-08-cycle-6-dogfood-findings.md`
§"Plugin MCP tools never reach the agent's tool surface" for
the full diagnosis.

### "`inspect` returns `internal_error` on an MPAS mesh file"

Was a cycle-6 bug (`358d44f`). Update to the current build —
inspect now returns `time = null` plus a `time_decode_failed`
warning instead of crashing on Time dims with no time
coordinate variable.

### "I asked for a plot of an MPAS variable but I get
`mesh_pairing_required`"

That's working as intended — the history file alone doesn't have
the geometry. Either:
- Re-prompt with the mesh file path: "use ocean_mesh.nc as the
  mesh", or
- Run inspect with the explicit `mesh_path=` first to confirm
  the pair, then ask for the plot.

### "I asked to plot a CICE file and the agent stopped"

CICE flattened block-decomposed grids (`ni=N, nj=1`) need the
matching CICE `grid.nc` file. Cycle 8 doesn't ship the unflatten
logic — cycle 9+ scope.

### "Slice produced an empty array, plot is blank"

The renderer returns `ambiguous` with `subcode: empty_slice`.
Usually: region bounds outside the file's coverage, or wrong
longitude convention. Check the inspect output's
`spatial.lon_convention` and re-ask with the correct region.

### "Plot looks washed out, the data is dominated by one extreme value"

Pass `clip_pct: [2, 98]` in your prompt: "Plot t2m, clip to the
2nd–98th percentile." The renderer also auto-clips when data
spans > 6 orders of magnitude (cycle-2 spec §7).

---

## 12. Remote file access via metplot-ssh-broker

For NetCDF files on remote hosts that require interactive
auth (RSA SecurID, Duo PIN+token, hosts that reject
ssh-agent / identity-file auth) — like OLCF's
`home.ccs.ornl.gov` — use **`metplot-ssh-broker`** so your
credential never enters the agent's chat context.

### Quickstart

In **your own terminal, BEFORE launching your agent**:

```bash
metplot-ssh-broker home.ccs.ornl.gov
```

You'll be prompted for your passcode. After auth, the
broker prints the socket path and stays running. Leave it
open (or background with `&`); `Ctrl-C` when you're done.

Then in your agent, reference remote files via `ssh://`
URLs as if they were local:

> **You**: Inspect `ssh://home.ccs.ornl.gov/autofs/nccs-svm1_proj/cli190/me/data/eam_h0.nc`.
>
> **Agent**: (auto-detects broker, calls `inspect` →
> routes through `broker.dump_header` → parses the CDL
> envelope without transferring the file)
> Found a CF-1.8 file with 47 variables. Header was
> 8.4 KB; full file is 1.2 GB and stayed remote.

> **You**: Map T2 from this file for the first time step.
>
> **Agent**: (broker stages the file locally via SFTP,
> then renders)
> Wrote `.metplot/plots/eam_T2_t0.png`.

Globs also work:

> **You**: Inspect `ssh://home.ccs.ornl.gov/data/era5_t2m_2024-*.nc`.
>
> **Agent**: (broker.glob_remote expands the pattern,
> classifier returns `kind: ssh_multi`)
> 12 monthly files matched. Combined time range
> 2024-01-01..2024-12-31.

### What the broker can do

| Capability | Behavior |
|---|---|
| File ops (SFTP-backed) | `listdir`, `stat`, `glob`, partial-read (`get_chunk`), full-fetch (`get_full`) |
| Header-only inspect | `inspect()` on `ssh://*.nc` runs `ncdump -h` remotely (~10 KB roundtrip) instead of transferring the whole file. Falls back to a full fetch if `ncdump` is missing on the remote host. |
| Read-only remote commands | Built-in allowlist: `ncdump`, `ls`, `cat`, `head`, `tail`, `wc`, `file`, `stat`. Extend with `--allow-exec=ncks,find` at broker start. |
| Remote glob expansion | `ssh://host/data/*.nc` expands via the broker to individual ssh URLs |

### What the broker won't do (by design)

- **Write operations**: `rm`, `mv`, `cp`, `mkdir`,
  `chmod`, shell redirection (`>`), pipes (`|`), command
  chaining (`&&` / `;`) — all blocked. `argv` is a list
  of strings, each `shlex.quote`d before joining for
  `transport.exec_command()`. No shell-metacharacter
  interpretation.
- **Auto-reconnect**: if the SSH transport dies (network
  blip, OLCF idle-kill), the broker reports
  `connection_lost` and exits within ~5 seconds. You
  restart with a fresh passcode.
- **Multi-host in one process**: one broker per remote.
  Run two brokers in two terminals for two remotes.
- **Concurrent operations**: all SFTP/exec ops serialize
  through a single SSH session channel — OLCF
  `MaxSessions=1` design contract.

### How the credential stays safe

1. You enter the passcode into the broker's
   `getpass.getpass()` prompt in your own terminal. It
   never echoes, never logs, never reaches stdout.
2. The broker passes the passcode to
   `paramiko.SSHClient.connect()` exactly once.
3. The local variable is overwritten and `del`-ed in
   `_authenticate()` before any other broker code runs.
4. The agent / MCP / Claude Code never sees the passcode
   — they only talk JSON-RPC to the broker's `0600` UNIX
   socket at `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock`.

For the protocol, channel state machine, and full threat
model, see `docs/architecture/ssh-broker.md`.

### Troubleshooting

> **"The agent asks me to set up the broker but I already
> did."**

The agent detects brokers via the socket file. Check:

```bash
ls -la $XDG_RUNTIME_DIR/metplot-ssh/
# or, without XDG_RUNTIME_DIR:
ls -la /tmp/metplot-ssh/
```

If the socket is missing, the broker isn't running (it
exited, or you started it for a different host). Re-run
`metplot-ssh-broker <host>` in your terminal.

> **`broker_required` envelope on `ssh://host/data/*.nc`.**

Remote glob expansion needs a broker — without one the
MCP can't reach the remote filesystem to list files.
Start the broker, then retry.

> **"Connection lost — broker exited."**

Restart the broker. OLCF's `ClientAliveInterval` may
idle-kill the TCP connection if there's no activity for
a while; the broker's default 30-second keepalive
usually handles this. If your site is stricter, lower
`--keepalive` to 15 or 10 seconds at start.

> **`tool not in exec allowlist: <name>`**

The agent tried to run a remote command that isn't in
the read-only allowlist. To allow a specific tool (e.g.
`ncks` for `ncks -m` metadata extraction), restart the
broker with `--allow-exec=ncks`. Writers (`rm`, `mv`,
`cp`, etc.) are not in the built-in allowlist; adding
them is your responsibility and is generally
discouraged.

> **"Two brokers, same host."**

The broker refuses to start if a socket already exists
at its discovery path. Kill the first broker (`Ctrl-C`
in its terminal, or `pkill -f 'metplot-ssh-broker
<host>'`) before starting a new one.

---

## 13. File-format support matrix

| Convention | Shape | inspect | plot map | plot timeseries | plot profile |
|---|---|---|---|---|---|
| CF-1.x (CMIP, ERA5, OISST, …) | rectilinear | ✓ | ✓ | ✓ | ✓ |
| CMIP6 | rectilinear | ✓ | ✓ | ✓ | ✓ |
| WRF | curvilinear + staggered + eta | ✓ | ✓ | ✓ | ✓ |
| ROMS | curvilinear + sigma | ✓ | ✓ | ✓ | ✓ |
| MPAS-Ocean | unstructured Voronoi | ✓ | ✓ (cycle 8) | (cycle 9+) | (cycle 9+) |
| MPAS-Atmosphere / MPAS-Seaice | unstructured Voronoi | ✓ | ✓ (cycle 8, inherits) | (cycle 9+) | (cycle 9+) |
| Omega | unstructured Voronoi | ✓ | ✓ (cycle 8) | (cycle 9+) | (cycle 9+) |
| E3SM EAMxx physics (`ncol`) | unstructured 1-D | partial | (cycle 9+) | (cycle 9+) | (cycle 9+) |
| E3SM EAMxx dycore (`elem×gp×gp`) | spectral-element | ✗ | ✗ (cycle 9+) | ✗ | ✗ |
| CICE5/6 (flattened `ni=N, nj=1`) | flattened block-decomposed | partial | ✗ (cycle 9+) | ✗ | ✗ |
| ICON | unstructured (varies) | (cycle 9+) | (cycle 9+) | (cycle 9+) | (cycle 9+) |
| FV3 | unstructured (cubed-sphere) | (cycle 9+) | (cycle 9+) | (cycle 9+) | (cycle 9+) |

**Remote sources**: HTTPS URLs (NetCDF-via-HTTP) and SSH paths
(`ssh://host/path/file.nc`) are supported by `inspect` and
`read_slice`. For OTP-protected SSH hosts (OLCF / ALCF /
NERSC), use **`metplot-ssh-broker`** so your credential never
enters the agent's context — see §12 above. Without a broker,
the MCP falls back to direct paramiko auth, which may prompt
for an identity file or password depending on the host's
config — that flow is preserved for non-OTP cases.

---

For the prompt-by-prompt feature coverage (~150 test cases), see
`docs/tester-guide.md`.

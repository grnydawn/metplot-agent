# metplot-agent

> NetCDF plotting via natural language, for AI coding agents.
> One source repo, seven build targets, MPAS-aware.

`metplot-agent` is a plugin you install into your AI coding agent
(Claude Code, Cursor, GitHub Copilot, Gemini CLI, Codex, Antigravity,
or Claude Desktop). After installing, you can say things like:

- "Inspect `/data/era5_t2m.nc`."
- "Plot the sea surface temperature for September 2024 over the North
  Atlantic."
- "Make a map of MPAS-Ocean Temperature using `ocean_mesh.nc` and
  `ocn.hist.0001-02-01_00.00.00.nc`."

and the agent walks the file, slices data, and renders a PNG.

## Status

Cycle 13 (shipped 2026-05-12) bundled four follow-on themes:
CICE/EAMxx cell-axis selectors, ELM/CPL map render, multi-cell
overlay + named-region lookup on unstructured grids, and
great-circle cross-section plots. Tool counts: netcdf-reader
14, plot-renderer 4. Current capability summary:

| Capability | Status |
|---|---|
| Rectilinear lat/lon maps (CMIP, ERA5) | shipping (cycle 3) |
| Curvilinear maps (WRF, ROMS) | shipping (cycle 3) |
| Unstructured Voronoi maps (MPAS-Ocean, MPAS-A, MPAS-Seaice, Omega, E3SM) | shipping (cycle 8) |
| CICE5/6 flattened block-decomposed grids (paired with grid file) | shipping (cycle 9) |
| EAMxx physics-column grid (paired with scrip-style grid file) | shipping (cycle 9) |
| E3SM Land Model (ELM) inspect detection | shipping (cycle 10) |
| E3SM Coupler (CPL) inspect detection | shipping (cycle 10) |
| Multi-file unstructured time-series (monthly globs + mesh) | shipping (cycle 10) |
| Time-decode fallback on undecodable time origins (year-0001 noleap) | shipping (cycle 10) |
| Unstructured time-series rendering (single cell / regional / global mean, MPAS family) | shipping (cycle 11) |
| Unstructured vertical profile rendering (cell-indexed, MPAS family) | shipping (cycle 11) |
| ncks-style analysis (hyperslab stride + dim reduction + CDL dump; bit-exact-vs-NCO tested) | shipping (cycle 12) |
| Unstructured cell-axis selectors for CICE (`ni`) + EAMxx (`ncol`) families | shipping (cycle 13) |
| ELM gridcell-level map render + CPL single-domain map render (closes detect-only gap) | shipping (cycle 13) |
| Multi-cell overlay timeseries + named-region lookup (`find_region`) on unstructured | shipping (cycle 13) |
| Great-circle cross-section plots (`slice_along_section` + `render_section`) on unstructured | shipping (cycle 13) |
| Time-series plots | shipping (cycle 3) |
| Vertical profiles + cross-sections | shipping (cycle 3) |
| Style-by-reference (extract style from a screenshot) | shipping (cycle 3) |
| Multi-file glob (time-concat) | shipping (cycle 3) |
| Style-refining skill-refiner loop (auto on Claude Code, manual elsewhere) | shipping (cycle 6) |
| 7 build targets (claude-code, cursor, copilot, gemini-cli, codex, antigravity, claude-desktop) | shipping (cycles 4 + 7) |
| Setup helper for Python deps (cartopy, scipy, MCP servers) | shipping (cycle 5) |

Out of scope this release (cycle 13+): EAMxx dycore
spectral-element grids (`elem × gp × gp`), ELM PFT-mosaic /
landunit / column-level visualization, CPL multi-domain
overlay rendering, CICE U-grid (velocity-on-edge) plotting,
region clipping on the unstructured map renderer itself
(cells_in_bbox + find_region cover the selector side; the
renderer still draws the full mesh), contour / streamline on
unstructured grids, time-animation of cross-sections,
interactive 3-D mesh viewers.

## Quickstart

The fastest path to a plot:

```bash
# 1. Clone
git clone https://github.com/grnydawn/metplot-agent.git
cd metplot-agent

# 2. Build for your host (pick one)
python -m tools.build claude-code

# 3. Follow the host-specific install steps below
```

After install, in your agent: **"Inspect `/path/to/your.nc`"** to
trigger the inspect skill, then **"Plot the temperature"** (or
whatever field) to render.

A full walkthrough lives in `docs/user-guide.md`. Feature-by-feature
test prompts in `docs/tester-guide.md`.

## Remote file access (OLCF and other OTP-protected hosts)

For NetCDF files on hosts that require interactive auth (RSA SecurID passcode, Duo PIN+token, etc.) — like OLCF's `home.ccs.ornl.gov` — use **metplot-ssh-broker** so your credential never enters the AI's context.

**One-time setup in your own terminal, BEFORE launching Claude Code:**

```bash
metplot-ssh-broker home.ccs.ornl.gov
```

You'll be prompted for your passcode. The broker:
- reads it via `getpass.getpass()` (never echoes, never logs)
- authenticates once via paramiko
- **drops the passcode from memory immediately** after `connect()`
- opens ONE SSH session channel and serializes SFTP + short-lived read-only exec through it (compatible with `MaxSessions=1`)
- exposes a `0600` UNIX socket at `$XDG_RUNTIME_DIR/metplot-ssh/<host>.sock`

**Then launch Claude Code.** Any `ssh://<host>/path` reference in your prompts is automatically routed through the broker — no credential enters the chat. When you're done, `Ctrl-C` the broker.

**Capabilities exposed via the broker:**
- File ops: listdir, stat, glob, partial-read, full-fetch
- Read-only remote commands (allowlist): `ncdump`, `ls`, `cat`, `head`, `tail`, `wc`, `file`, `stat`
- Extend the allowlist with `--allow-exec=ncks,find`

**Bandwidth-saving fast path:** `inspect()` on an `ssh://*.nc` path issues `ncdump -h` remotely and parses the CDL header (~10 KB) instead of transferring the whole file. Falls back to a full fetch if `ncdump` is missing on the remote host.

**Limits:**
- SFTP + short-lived read-only exec — no remote shell, no write operations
- One broker per host — run multiple brokers for multiple remotes
- No auto-reconnect — if the connection dies, restart the broker (and re-enter the passcode in your terminal)

See `docs/architecture/ssh-broker.md` for the full design.

## Install per host

> The build output for every target lands at `build/<target>/`.
> Each build dir ships its own self-contained `README.md` with
> host-specific install instructions; the sections below are the
> condensed version.

### Claude Code

```bash
python -m tools.build claude-code
```

In Claude Code:

```
/plugin marketplace add /absolute/path/to/metplot-agent/build/claude-code
/plugin install metplot@metplot-local
```

Restart Claude Code. The bundled `SessionStart` hook auto-runs
`setup.sh --quiet` on first launch, which installs the Python
deps the MCP servers need.

Verify: type `/` in the prompt and check that `/metplot:setup`
and `/metplot:refine` appear in the completion menu.

### Cursor

```bash
python -m tools.build cursor
pip install ./build/cursor/metplot/mcp-servers/netcdf_reader
pip install ./build/cursor/metplot/mcp-servers/plot_renderer
```

Copy `build/cursor/metplot/` to `~/.cursor/extensions/metplot/`
(or use Cursor's "Install Extension from Source" flow). Restart
Cursor.

### GitHub Copilot (VS Code)

```bash
python -m tools.build copilot
pip install ./build/copilot/metplot/mcp-servers/netcdf_reader
pip install ./build/copilot/metplot/mcp-servers/plot_renderer
```

In VS Code: Chat → "Install Plugin From Source" → select
`build/copilot/metplot/`. (Or copy to `~/.copilot/plugins/metplot/`
and reload.) Restart VS Code.

### Gemini CLI

```bash
python -m tools.build gemini-cli
pip install ./build/gemini-cli/metplot/mcp-servers/netcdf_reader
pip install ./build/gemini-cli/metplot/mcp-servers/plot_renderer
gemini extensions install ./build/gemini-cli/metplot
```

Merge the `mcpServers` block from the bundled `settings.json` into
`~/.gemini/settings.json`. Restart any open Gemini CLI sessions.

### Codex CLI / Codex Desktop

```bash
python -m tools.build codex
pip install ./build/codex/metplot/mcp-servers/netcdf_reader
pip install ./build/codex/metplot/mcp-servers/plot_renderer
```

Copy `build/codex/metplot/` to `~/.codex/plugins/metplot/` and
append the contents of its `config.toml` to `~/.codex/config.toml`.
Restart Codex.

> Codex's user-defined slash command authoring format isn't
> documented as of May 2026 — `/refine` doesn't ship for Codex.
> The `skill-refiner` skill is in the bundle and can be invoked
> manually.

### Antigravity

```bash
python -m tools.build antigravity
pip install ./build/antigravity/metplot/mcp-servers/netcdf_reader
pip install ./build/antigravity/metplot/mcp-servers/plot_renderer
```

Copy `build/antigravity/metplot/.agent/` into your project root
(or to `~/.gemini/antigravity/` for global install). Merge the
bundled `mcp_config.json` into Antigravity's MCP config.

### Claude Desktop

```bash
python -m tools.build claude-desktop
pip install ./build/claude-desktop/metplot/mcp-servers/netcdf_reader
pip install ./build/claude-desktop/metplot/mcp-servers/plot_renderer
```

- Paste `build/claude-desktop/metplot/project_instructions.md`
  into your Claude Project's Custom Instructions.
- Merge `build/claude-desktop/metplot/claude_desktop_config_snippet.json`
  into `~/Library/Application Support/Claude/claude_desktop_config.json`
  (macOS) or the platform equivalent.
- Restart Claude Desktop.

## Uninstall (clean reinstall)

If you're upgrading from an older `metplot-agent` install (or
something is broken and you want a fresh start), uninstall the
previous version first, then run the install steps above. Order
matters — uninstall the host plugin/extension before removing
the MCP servers, so the agent's MCP launch stanzas drop before
the Python packages disappear underneath them.

### MCP servers (all hosts)

```bash
pip uninstall metplot-netcdf-reader metplot-plot-renderer
```

This drops the `metplot-netcdf-reader` and `metplot-plot-renderer`
entry-point scripts from `PATH`. Verify with `which
metplot-netcdf-reader` (should be empty).

### Claude Code

```
/plugin uninstall metplot
/plugin marketplace remove metplot-local
```

Then close Claude Code and delete the cached plugin payload:

```bash
rm -rf ~/.claude/plugins/cache/metplot-local
```

### Cursor

Remove the extension dir:

```bash
rm -rf ~/.cursor/extensions/metplot
```

Open Cursor → Extensions → reload if Cursor still shows it.

### GitHub Copilot (VS Code)

VS Code → Extensions panel → find "metplot" → Uninstall. Then:

```bash
rm -rf ~/.copilot/plugins/metplot   # if you copied manually
```

Restart VS Code.

### Gemini CLI

```bash
gemini extensions remove metplot
rm -rf ~/.gemini/extensions/metplot
```

Remove the metplot block from `mcpServers` in
`~/.gemini/settings.json`.

### Codex CLI / Codex Desktop

```bash
rm -rf ~/.codex/plugins/metplot
```

Edit `~/.codex/config.toml` and remove the `[mcp_servers.metplot-netcdf-reader]`
and `[mcp_servers.metplot-plot-renderer]` blocks. Restart Codex.

### Antigravity

```bash
rm -rf .agent/skills/metplot          # project-local install
rm -rf ~/.gemini/antigravity/metplot  # global install (if used)
```

Remove the metplot block from Antigravity's `mcp_config.json`.

### Claude Desktop

- Delete the metplot block from your Claude Project's Custom
  Instructions.
- Remove the `metplot-netcdf-reader` and `metplot-plot-renderer`
  entries from `claude_desktop_config.json` under `mcpServers`.
- Restart Claude Desktop.

### Workspace state (optional)

`metplot-agent` writes per-project state under `.metplot/` in
whatever directory you launch the agent from:

```
.metplot/
├── inspections/      cached inspect envelopes (mtime-keyed)
├── slices/           materialized slice files when too big to inline
├── task-log.jsonl    skill-refiner observation log
└── refinements/      pending refinement drafts (and applied/ archive)
```

To start completely fresh, delete `.metplot/` after uninstalling:

```bash
rm -rf .metplot
```

## Next steps

- **First-time users**: read `docs/user-guide.md` for a guided
  walkthrough — installation reminders, the inspect → slice →
  render pipeline, plotting recipes (rectilinear / WRF / ROMS /
  MPAS), style-by-reference, the refiner loop, troubleshooting.
- **Testers and QA**: `docs/tester-guide.md` lists ~150 prompt →
  expected-output pairs covering every shipped feature, organized
  by capability.
- **Contributors**: `docs/architecture.md` describes the L1/L2/L3
  layering, `docs/adding-targets.md` covers shipping to a new
  host, `docs/self-improvement.md` covers the skill-refiner loop.

## License

MIT — see `LICENSE`.

# Installation

How to install `metplot-agent` into each of the seven supported AI agent
hosts: **Claude Code, Cursor, GitHub Copilot, Gemini CLI, Codex,
Antigravity, and Claude Desktop**.

`metplot-agent` is one source repo that builds into seven host-specific
plugin payloads. You build the payload for your host with
`python -m tools.build <target>`, install it where your host expects
plugins, then enable the skills and the two MCP servers (the **netcdf
reader** and the **plot renderer**). The MCP servers are Python packages;
their dependencies are installed either automatically (Claude Code) or
with the `metplot:setup` skill / a `pip install`.

The condensed per-host steps also live in the
[README](../README.md#install-per-host); this document is the full
reference, including prerequisites, dependency setup, and a per-host
"verify it works" check.

---

## Prerequisites

Before building or installing any target:

- **Python ≥ 3.10** on your `PATH` (`python --version`). The MCP servers,
  the build tool, and `cartopy` all require it.
- **A C/C++ toolchain and the system libraries `cartopy` needs.** `cartopy`
  builds on top of **GEOS** and **PROJ**; `netcdf4` needs the **NetCDF** and
  **HDF5** C libraries. On most platforms `pip` pulls prebuilt wheels and you
  need nothing extra, but if a wheel is unavailable for your platform you'll
  need the system packages:
  - **Debian / Ubuntu:** `sudo apt-get install libgeos-dev libproj-dev libnetcdf-dev libhdf5-dev`
  - **macOS (Homebrew):** `brew install geos proj netcdf hdf5`
  - **conda (any OS):** `conda install -c conda-forge geos proj cartopy netcdf4`
- **`git`**, to clone the repo.
- The AI agent host you're installing into (Claude Code, Cursor, etc.).

Clone the repo once; every build target is produced from it:

```bash
git clone https://github.com/grnydawn/metplot-agent.git
cd metplot-agent
```

`python -m tools.build --list` prints every buildable target. The build
output for each target lands at `build/<target>/`, and each build dir
ships its own self-contained `README.md` with host-specific notes.

---

## Python dependencies for the MCP servers

The two MCP servers — **netcdf reader** and **plot renderer** — need a set
of scientific Python packages. They're declared as the `mcp`
extra in [`pyproject.toml`](../pyproject.toml):

| Package | Why |
|---|---|
| `mcp>=1.0` | MCP server framework (the protocol the host speaks) |
| `xarray>=2024.1` | NetCDF dataset model used by the reader |
| `netcdf4>=1.6` | NetCDF/HDF5 file I/O backend |
| `numpy>=1.24` | array math for slicing and stats |
| `matplotlib>=3.8` | figure rendering for the plot renderer |
| `cartopy>=0.22` | map projections / coastlines for geographic plots |

You have two ways to install these:

### Automated path — the `metplot:setup` skill (recommended)

After installing a host plugin that exposes skills (claude-code,
gemini-cli, cursor, copilot, antigravity), run the **`metplot:setup`**
skill from inside the agent:

```
/metplot:setup
```

It installs/refreshes the two MCP server packages plus `cartopy` and
`scipy` into the metplot virtualenv, and is idempotent — safe to re-run.
On **Claude Code** this even runs automatically: the bundled
`SessionStart` hook fires `setup.sh --quiet` on first launch, so you
usually don't have to invoke it by hand.

> Codex and Claude Desktop don't run user skills the same way; for those
> two, use the manual path below.

### Manual path — `pip install`

For any host (and required for Codex and Claude Desktop), install the two
MCP server packages directly. Each build payload vendors them under
`build/<target>/metplot/mcp-servers/`:

```bash
pip install ./build/<target>/metplot/mcp-servers/netcdf_reader
pip install ./build/<target>/metplot/mcp-servers/plot_renderer
```

Both packages declare the `mcp` extra as their dependency set, so this
pulls `xarray`, `netcdf4`, `numpy`, `matplotlib`, and `cartopy` along
with them.

To install the extra straight from the repo without building a target
(useful for development), use:

```bash
pip install -e ".[mcp]"
```

---

## Per-host installation

Each section below: **build → install/point → enable skills + MCP
servers → verify**.

### Claude Code

**Build:**

```bash
python -m tools.build claude-code
```

**Install / point.** In Claude Code:

```
/plugin marketplace add /absolute/path/to/metplot-agent/build/claude-code
/plugin install metplot@metplot-local
```

Restart Claude Code.

**Enable skills + MCP servers.** The bundled `SessionStart` hook
auto-runs `setup.sh --quiet` on first launch, which installs the MCP
server dependencies (the `mcp` extra) automatically. If it didn't run,
invoke `/metplot:setup` manually. The two MCP servers are launched by the
plugin's `.mcp.json`; the skills ship inside the plugin payload.

**Verify it works.** Type `/` and confirm `/metplot:setup` and
`/metplot:refine` appear in the completion menu. Then ask the agent:

```
Inspect data/<a sample>.nc
Plot the temperature.
```

A successful inspect lists the file's variables/dimensions and a
successful plot writes a PNG.

### Cursor

**Build:**

```bash
python -m tools.build cursor
```

**Install / point.** Copy `build/cursor/metplot/` to
`~/.cursor/extensions/metplot/` (or use Cursor's "Install Extension from
Source" flow), then restart Cursor.

**Enable skills + MCP servers.** Install the two MCP server packages:

```bash
pip install ./build/cursor/metplot/mcp-servers/netcdf_reader
pip install ./build/cursor/metplot/mcp-servers/plot_renderer
```

Or run `/metplot:setup` from inside Cursor. The skills load from the
copied extension dir.

**Verify it works.** Ask Cursor's agent to **inspect a sample `.nc`
file**, then **render a plot** of one of its variables; confirm the
inspect lists variables and the plot produces a PNG.

### GitHub Copilot (VS Code)

**Build:**

```bash
python -m tools.build copilot
```

**Install / point.** In VS Code: Chat → "Install Plugin From Source" →
select `build/copilot/metplot/`. (Or copy to `~/.copilot/plugins/metplot/`
and reload.) Restart VS Code.

**Enable skills + MCP servers:**

```bash
pip install ./build/copilot/metplot/mcp-servers/netcdf_reader
pip install ./build/copilot/metplot/mcp-servers/plot_renderer
```

Or run `/metplot:setup` from the Copilot chat.

**Verify it works.** Ask Copilot chat to **inspect a sample `.nc` file**
and **render a plot**; confirm variables are listed and a PNG is written.

### Gemini CLI

**Build:**

```bash
python -m tools.build gemini-cli
```

**Install / point:**

```bash
gemini extensions install ./build/gemini-cli/metplot
```

Merge the `mcpServers` block from the bundled `settings.json` into
`~/.gemini/settings.json`, then restart any open Gemini CLI sessions.

**Enable skills + MCP servers:**

```bash
pip install ./build/gemini-cli/metplot/mcp-servers/netcdf_reader
pip install ./build/gemini-cli/metplot/mcp-servers/plot_renderer
```

Or run `/metplot:setup`. The `mcpServers` block you merged points Gemini
at the two servers.

**Verify it works.** In a Gemini CLI session, ask it to **inspect a
sample `.nc` file** then **plot a variable**; confirm the inspect output
and a rendered PNG.

### Codex CLI / Codex Desktop

**Build:**

```bash
python -m tools.build codex
```

**Install / point.** Copy `build/codex/metplot/` to
`~/.codex/plugins/metplot/` and append the contents of its `config.toml`
to `~/.codex/config.toml`. Restart Codex.

**Enable skills + MCP servers.** Codex doesn't run the `metplot:setup`
skill, so install the MCP server packages manually:

```bash
pip install ./build/codex/metplot/mcp-servers/netcdf_reader
pip install ./build/codex/metplot/mcp-servers/plot_renderer
```

The `[mcp_servers.*]` blocks you appended to `config.toml` launch the two
servers.

> Codex's user-defined slash-command format isn't documented as of this
> writing, so `/refine` doesn't ship for Codex. The `skill-refiner` skill
> is still in the bundle and can be invoked manually.

**Verify it works.** Ask Codex to **inspect a sample `.nc` file** and
**render a plot**; confirm variables are listed and a PNG is produced.

### Antigravity

**Build:**

```bash
python -m tools.build antigravity
```

**Install / point.** Copy `build/antigravity/metplot/.agent/` into your
project root (or to `~/.gemini/antigravity/` for a global install). Merge
the bundled `mcp_config.json` into Antigravity's MCP config.

**Enable skills + MCP servers:**

```bash
pip install ./build/antigravity/metplot/mcp-servers/netcdf_reader
pip install ./build/antigravity/metplot/mcp-servers/plot_renderer
```

Or run `/metplot:setup`. The merged `mcp_config.json` registers the two
servers; the skills load from the copied `.agent/` dir.

**Verify it works.** Ask the Antigravity agent to **inspect a sample
`.nc` file** then **plot a variable**; confirm the inspect output and a
rendered PNG.

### Claude Desktop

**Build:**

```bash
python -m tools.build claude-desktop
```

**Install / point.**

- Paste `build/claude-desktop/metplot/project_instructions.md` into your
  Claude Project's Custom Instructions.
- Merge
  `build/claude-desktop/metplot/claude_desktop_config_snippet.json` into
  `~/Library/Application Support/Claude/claude_desktop_config.json`
  (macOS) or the platform equivalent.
- Restart Claude Desktop.

**Enable skills + MCP servers.** Claude Desktop doesn't run the
`metplot:setup` skill, so install the MCP server packages manually:

```bash
pip install ./build/claude-desktop/metplot/mcp-servers/netcdf_reader
pip install ./build/claude-desktop/metplot/mcp-servers/plot_renderer
```

The `mcpServers` entries you merged into `claude_desktop_config.json`
launch the two servers; the skills are folded into the pasted project
instructions.

**Verify it works.** In your Claude Project, ask it to **inspect a sample
`.nc` file** and then **render a plot** of a variable; confirm the
inspect lists variables and a PNG is produced.

---

## Troubleshooting

- **A skill doesn't appear (`/metplot:setup` missing from autocomplete).**
  Confirm the host plugin installed and you restarted the host. See the
  troubleshooting section of [`docs/user-guide.md`](user-guide.md).
- **`cartopy` or `netcdf4` failed to install.** Install the system libs
  from [Prerequisites](#prerequisites) (GEOS, PROJ, NetCDF, HDF5), or use
  the conda-forge packages, then re-run `/metplot:setup` or the `pip
  install` steps.
- **A plot fails to render.** Re-run `/metplot:setup` to refresh
  `matplotlib`/`cartopy`, and confirm the plot-renderer MCP server is
  registered in your host's MCP config.

## Next steps

- New users: [`docs/user-guide.md`](user-guide.md) — guided walkthrough
  of the inspect → slice → render pipeline.
- Testers/QA: [`docs/tester-guide.md`](tester-guide.md) — prompt →
  expected-output pairs for every feature.
- Contributors: [`docs/architecture.md`](architecture.md) and
  [`docs/adding-targets.md`](adding-targets.md).

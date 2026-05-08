# Cycle 4 — Claude Code target (per-host packager)

> Design for cycle 4 of `ncplot-agent`. Builds the per-host packager
> that turns the canonical L1 source (skills, MCP servers, reference
> data) into an installable Claude Code plugin payload.

**Status:** approved by delegation
**Date:** 2026-05-08
**Branch:** `cycle-4-claude-code`

---

## 1. Overview

Cycle 4 makes the work installable. After cycle 3 the L1 source is
complete (2 MCP servers + 5 skills + reference data + 542 tests), but
nothing is yet packaged for a specific agent host. Cycle 4 ships the
first per-host target: **Claude Code**.

### What ships

- **Working `targets/claude-code/build.py`** that produces a valid
  Claude Code plugin payload at `build/claude-code/ncplot-agent/`
  containing:
  - `.claude-plugin/plugin.json` (manifest)
  - `skills/` — direct copy of `src/skills/`
  - `mcp-servers/` — bundled MCP server source
  - `.mcp.json` — MCP launch stanzas
  - `commands/` — `/refine` placeholder slash command (stub for cycle 6)
  - `README.md` — install + setup instructions
- **MCP launch contract** that actually works: launch commands invoke
  the MCP servers via their installed entry-point scripts
  (`ncplot-netcdf-reader`, `ncplot-plot-renderer`) — relying on `pip
  install` of the bundled `mcp-servers/<name>/` packages.
- **Build-output validation tests** (`tests/targets/claude-code/`)
  covering: directory structure, plugin.json schema, .mcp.json schema,
  skills copied correctly, MCP servers importable.
- **MCP smoke tests** that verify each bundled server can be imported
  without errors and lists its tools.
- **Documentation update** — README at `targets/claude-code/README.md`
  + a short install guide.
- **`tools/build.py` improvements** — better error messages, status
  output, optional `--validate` flag that runs the build-output tests.

### What does NOT ship

- **Stop hook for skill-refiner.** Cycle 6 owns this. Cycle 4 omits the
  hook entirely (the plugin still works; refinement is just unavailable
  until cycle 6).
- **`/refine` slash command implementation.** Cycle 4 ships a
  placeholder stub; the actual refinement logic is cycle 6.
- **Marketplace publishing / signed releases.** Cycle 4 produces a
  local install artifact only.
- **Auto-installer for Python deps** (cartopy, scipy, etc.). Cycle 5
  closes that gap.
- **Hermes / Codex / Cursor / Claude Desktop targets.** The other
  three target dirs already have stubs but their full implementation
  is out of scope for cycle 4.

### Primary use case

A developer or end-user wants to install ncplot-agent into their local
Claude Code:

1. Clone the repo.
2. Run `python -m tools.build claude-code`.
3. `cp -r build/claude-code/ncplot-agent ~/.claude/plugins/`
4. Inside the plugin dir: `pip install ./mcp-servers/netcdf_reader
   ./mcp-servers/plot_renderer` (sets up entry-point scripts).
5. Restart Claude Code. The skills + MCP tools are available.

### Non-goals

- Not building a Python skill-loader / runtime (skills are still
  declarative; the host LLM consumes them).
- Not changing cycle 1/2 MCP server APIs.
- Not introducing new MCP tools.
- Not building a CI pipeline (future cycle).

---

## 2. Plugin payload structure

```
build/claude-code/ncplot-agent/
├── .claude-plugin/
│   └── plugin.json              # manifest
├── README.md                    # install + setup instructions (auto-generated)
├── skills/                      # direct copies of src/skills/<name>/
│   ├── netcdf-inspect/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── netcdf-plot-router/
│   │   └── SKILL.md
│   ├── netcdf-plot-map/
│   │   ├── SKILL.md
│   │   └── references/
│   ├── netcdf-plot-timeseries/
│   │   └── SKILL.md
│   └── netcdf-plot-profile/
│       └── SKILL.md
├── mcp-servers/                 # bundled MCP server packages (installable)
│   ├── netcdf_reader/
│   │   ├── pyproject.toml
│   │   ├── src/                 # SEE §3 — import path strategy
│   │   └── README.md
│   └── plot_renderer/
│       ├── pyproject.toml
│       ├── src/
│       └── README.md
├── .mcp.json                    # MCP launch stanzas
└── commands/
    └── refine.md                # placeholder /refine command
```

### Note: skill-refiner is NOT included in cycle 4

`src/skills/skill-refiner/` exists in the repo (a stub from cycle 0).
The cycle-4 build EXCLUDES it from the plugin payload — it isn't
implemented and shouldn't be exposed to the host LLM yet. Cycle 6 adds
it back.

---

## 3. MCP server packaging strategy

The cycle 1/2 MCP servers live at `src/mcp/netcdf_reader/` and
`src/mcp/plot_renderer/` in the repo. Their `server.py` files import
from `src.mcp.netcdf_reader.*` etc. — absolute imports rooted at the
repo's `src/` directory.

When packaged into the plugin at `mcp-servers/<name>/`, this path
resolution breaks unless the plugin file layout preserves the
`src/mcp/<name>/` prefix.

### 3.1 Approach: ship as installable Python packages

The MCP servers ALREADY have `pyproject.toml` files with proper
package metadata + entry-point scripts (`ncplot-netcdf-reader`,
`ncplot-plot-renderer`). The cleanest approach is to ship them as
installable distributions.

**Bundled layout per server** (in plugin payload):

```
mcp-servers/netcdf_reader/
├── pyproject.toml          # copied from src/mcp/netcdf_reader/pyproject.toml
├── README.md
└── src/                    # NEW — re-rooted at this point
    └── mcp/
        └── netcdf_reader/  # copy of src/mcp/netcdf_reader/ (with __init__.py etc)
            ├── __init__.py
            ├── adapter.py
            ├── envelope.py
            ├── server.py
            └── ... (all files)
```

That preserves the `src.mcp.netcdf_reader.*` import path so existing
code works without modification.

After install (`pip install ./mcp-servers/netcdf_reader`), the entry
point `ncplot-netcdf-reader` runs the MCP server.

### 3.2 Bundled pyproject.toml needs path remapping

The cycle-1/2 `pyproject.toml` files use `name = "netcdf-reader"` and
`name = "plot-renderer"`. The packages `src.mcp.netcdf_reader` and
`src.mcp.plot_renderer` need to be discoverable by setuptools.

**Cycle-4 build adds a `[tool.setuptools]` block** specifying:

```toml
[tool.setuptools.packages.find]
where = ["src"]
namespaces = true
```

So `pip install` from the bundled directory finds the packages under
`src/`.

We do this by either copying the existing pyproject.toml verbatim and
patching it, or generating a new one. Patching is simpler and survives
upstream changes — done in `build.py`.

### 3.3 `.mcp.json` launch stanzas

The launch command uses the entry-point script:

```json
{
  "mcpServers": {
    "netcdf-reader": {
      "command": "ncplot-netcdf-reader",
      "args": []
    },
    "plot-renderer": {
      "command": "ncplot-plot-renderer",
      "args": []
    }
  }
}
```

This assumes the user's PATH includes the install location (typical
after `pip install`).

### 3.4 Fallback for users who don't want pip install

If the user prefers not to install, they can add a `python -m` invocation:

```json
{
  "mcpServers": {
    "netcdf-reader": {
      "command": "python",
      "args": ["-m", "src.mcp.netcdf_reader.server"]
    }
  }
}
```

But this requires `${CLAUDE_PLUGIN_ROOT}/mcp-servers/netcdf_reader/src/`
on `PYTHONPATH`. The plugin README documents both options.

**Default in cycle 4:** the entry-point script approach (§3.3). The
fallback is documented, not generated.

---

## 4. plugin.json manifest

```json
{
  "$schema": "https://json.schemastore.org/claude-code-plugin",
  "name": "ncplot-agent",
  "version": "0.1.0",
  "description": "Natural-language plotting from NetCDF files. Maps, time series, and vertical profiles. WRF/ROMS/CMIP/reanalysis aware.",
  "author": {
    "name": "ncplot-agent contributors"
  },
  "homepage": "https://github.com/grnydawn/ncplot-agent",
  "license": "MIT",
  "keywords": ["netcdf", "matplotlib", "cartopy", "wrf", "roms", "cmip", "climate"],
  "ncplot": {
    "build_cycle": 4,
    "ships_skills": [
      "netcdf-inspect",
      "netcdf-plot-router",
      "netcdf-plot-map",
      "netcdf-plot-timeseries",
      "netcdf-plot-profile"
    ],
    "ships_mcp_servers": ["netcdf-reader", "plot-renderer"]
  }
}
```

The `ncplot` block is a custom namespace for our internal validation
tests. Claude Code ignores unknown manifest fields per its plugin
schema.

---

## 5. /refine slash command (placeholder)

`commands/refine.md`:

```markdown
---
description: Review the current session and propose refinement drafts to the canonical skills. (Currently a placeholder — full implementation lands in cycle 6.)
---

The `/refine` command will trigger the `skill-refiner` skill (cycle 6)
once that's implemented. For now, this is a placeholder so the command
appears in autocomplete.

Until cycle 6 ships:

- The task-log at `.ncplot/task-log.jsonl` is being written by skills
  on user corrections.
- No automatic refinement happens.
- No drafts are produced.

After cycle 6: this command will invoke skill-refiner against the
session log and produce draft refinements under `.ncplot/refinements/`
for human review.
```

This is a stub that explicitly tells the user the feature isn't ready.
Better than silently doing nothing.

---

## 6. Hooks: deferred to cycle 6

The existing build.py stub creates a `Stop` hook that fires the
skill-refiner. Cycle 6 ships skill-refiner. **Cycle 4 omits the hook
entirely** — no `hooks/` directory, no hook config in plugin.json.

Reason: a hook that fires on every session end and tells the agent
"run skill-refiner" when skill-refiner doesn't exist would be noise.
Better to ship the hook with the feature.

---

## 7. Build process

### 7.1 Existing dispatcher (kept)

`tools/build.py` is already in place. It:
- Discovers targets via `targets/<name>/build.py`
- Calls `build(src_root, out_root)` from each
- Outputs to `build/<target>/`

Cycle 4 keeps this unchanged but adds a `--validate` flag.

### 7.2 `--validate` flag

After building, run `tests/targets/<target>/test_build_output.py`
against the produced artifact:

```
python -m tools.build claude-code --validate
```

If validation fails, `--validate` returns non-zero and prints the
failures. Without `--validate`, build is fire-and-forget.

### 7.3 build.py rewrite (cycle 4's main code change)

The existing `targets/claude-code/build.py` works for the basic shape
but has the import-path bug. Cycle 4 rewrites it to:

1. Create the plugin dir, manifest, `.claude-plugin/plugin.json`
2. Copy skills from `src/skills/` — **excluding `skill-refiner`**
3. For each MCP server in `src/mcp/`:
   - Create `mcp-servers/<name>/`
   - Copy `pyproject.toml` (patched to add `[tool.setuptools.packages.find]`)
   - Copy README.md if present
   - Re-root the package source under `src/mcp/<name>/`
4. Write `.mcp.json` with entry-point launch commands
5. Write `commands/refine.md` placeholder
6. Write `README.md` with install instructions
7. Skip hooks/

### 7.4 Build is idempotent + reproducible

- `build/` is .gitignored
- Build cleans the target dir before writing
- No randomness, no timestamps in output (the tests check this)

---

## 8. Tests

### 8.1 Build-output validation (`tests/targets/claude-code/`)

`test_build_runs.py` — the build itself succeeds:

```python
def test_build_produces_expected_output(tmp_path):
    from targets.claude_code import build as ccbuild
    src_root = REPO_ROOT / "src"
    ccbuild.build(src_root, tmp_path)
    plugin_root = tmp_path / "ncplot-agent"
    assert plugin_root.is_dir()
    assert (plugin_root / ".claude-plugin" / "plugin.json").is_file()
    ...
```

`test_manifest_schema.py` — `plugin.json` parses, has required fields.

`test_skills_copied.py` — every cycle-3 skill present, frontmatter
preserved, references/ subdirs intact. `skill-refiner` is NOT present.

`test_mcp_servers_bundled.py` — every cycle-1/2 MCP server is bundled
under `mcp-servers/<name>/` with `pyproject.toml` patched correctly.

`test_mcp_json_schema.py` — `.mcp.json` parses, has required keys,
launch commands point to entry-point scripts.

`test_commands_dir.py` — `commands/refine.md` exists and has valid
frontmatter.

`test_no_hooks.py` — `hooks/` directory does NOT exist (deferred to cycle 6).

### 8.2 MCP smoke tests

`test_mcp_smoke.py` — for each bundled server:
- The server module is importable from the bundled path
- `list_tool_names()` returns the expected list
- `dispatch()` is callable

This proves the import-path remapping (§3.1) actually works.

### 8.3 Build dispatcher tests (`tests/tools/`)

`test_build_dispatcher.py` — `tools/build.py` discovers targets,
builds claude-code, and `--validate` runs the validation suite.

### 8.4 What we don't test

- The plugin actually loading inside Claude Code. That's an end-to-end
  test we can't run in CI without a real Claude Code instance. Cycle 4
  ships a manual test plan in the PR body.
- The MCP servers running over stdio. Same — that's a process-level
  integration test that would require fork-exec. The smoke test
  verifies the import path; the actual stdio loop is cycle 1/2's job.
- Hot-reload, version upgrades. Future cycle.

---

## 9. Open risks

### 9.1 Claude Code plugin format drift

**Risk:** Anthropic changes the plugin manifest schema.

**Response:** The validation test (`test_manifest_schema.py`) pins our
expected shape. If Anthropic changes the schema, the test fails and we
fix the build.

### 9.2 Entry-point launch fails on user's machine

**Risk:** User installs the plugin but doesn't `pip install` the
mcp-servers; launch commands fail because `ncplot-netcdf-reader` isn't
on PATH.

**Response:** README documents the pip install step prominently. A
follow-up cycle (cycle 5) adds an auto-installer that runs on first
plugin load.

### 9.3 setuptools package discovery

**Risk:** `[tool.setuptools.packages.find]` with `where = ["src"]` and
`namespaces = true` may not work on all setuptools versions, or may
discover unexpected packages.

**Response:** The smoke test catches this — if the package isn't
installable, the test fails. Pin to setuptools >= 68 (already in cycle
1/2 deps).

### 9.4 Skill-refiner stub leakage

**Risk:** `src/skills/skill-refiner/` exists in the repo. If the build
accidentally includes it, the plugin advertises a skill that does
nothing.

**Response:** `test_skills_copied.py` explicitly asserts skill-refiner
is NOT in the build output. Build code uses an explicit allowlist.

### 9.5 Cross-platform line endings

**Risk:** Built JSON / hooks may have CRLF on Windows.

**Response:** All Write calls use Python's default text mode (LF on
all platforms). Tests verify with `read_bytes()` and check for `\r\n`.
This is a stretch concern; not enforced unless real Windows users hit
it.

### 9.6 Build artifact in source tree

**Risk:** `build/` directory accumulates state and pollutes git status.

**Response:** Already gitignored at the repo level (verify in
test_build_output). Build is idempotent so re-running is safe.

---

## 10. Cross-cutting principles

### 10.1 Inherited from cycles 1-3

1. **TDD per task.**
2. **Atomic commits.**
3. **Envelope discipline** in any MCP-touching code (cycle 4 doesn't
   touch MCP code, only packages it).

### 10.2 New for cycle 4

4. **Build is idempotent.** Re-running the build over an existing
   output dir produces the same result; old contents are wiped.
5. **No build artifact in version control.** `build/` is gitignored.
   Validation runs against a temp-dir build, not against committed
   bytes.
6. **Per-target builds are independent.** Failing claude-code build
   doesn't affect codex / hermes / etc.
7. **Entry-point launch over inline python -m.** Keeps `.mcp.json`
   simple; documented fallback for users who can't install.
8. **Skill-refiner stays out of the build until cycle 6.** Same for
   the Stop hook.
9. **Validation is a flag, not the default.** Build is fast; `--validate`
   is for CI / pre-release.

### 10.3 What cycle 4 does NOT establish

- A signed release format
- A marketplace listing
- A plugin update mechanism
- A non-Claude-Code target (cycle 4 is single-target; future cycles
  may extend the same pattern to claude-desktop / codex / hermes / cursor)

---

## End of spec

Implementation plan goes in
`docs/plans/2026-05-08-cycle-4-claude-code.md`.

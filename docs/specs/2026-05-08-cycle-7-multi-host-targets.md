# Cycle 7 — Multi-host target expansion

> Design for cycle 7. Adds 5 new build targets (Codex CLI/Desktop, Gemini
> CLI, Cursor, GitHub Copilot, Antigravity) plus a polish pass on Claude
> Desktop. Reuses the cycle-4 build pattern; extracts shared logic into
> `targets/_common/` so each new target is a small, focused build.py.

**Status:** approved by delegation
**Date:** 2026-05-08
**Branch:** `cycle-7-multi-host-targets`
**Research:** `docs/research/2026-05-08-multi-host-survey.md`

---

## 1. Overview

After cycle 4, ncplot-agent ships for one host (Claude Code). The
research in `docs/research/2026-05-08-multi-host-survey.md` confirms
that 5 more major hosts (Codex, Gemini CLI, Cursor, GitHub Copilot,
Antigravity) all natively load `SKILL.md` and stdio MCP — so porting
is mechanical, not architectural. Cycle 7 ships all of them.

### What ships

- **Shared build helpers** at `targets/_common/`:
  - `mcp_bundling.py` — re-rooted MCP server packaging (extracted from
    cycle 4, used by every target that bundles MCP servers)
  - `skills.py` — skills allowlist + copy helper
  - `manifest.py` — shared metadata
- **6 build targets** (5 new + 1 refactored):
  - `targets/codex/build.py` — rewritten (was AGENTS.md stub) to emit
    `.codex-plugin/plugin.json` with native SKILL.md + `config.toml` MCP
  - `targets/gemini-cli/build.py` — NEW; emits `gemini-extension.json`
    with `settings.json` MCP + `commands/refine.toml`
  - `targets/cursor/build.py` — NEW; emits `.cursor-plugin/plugin.json`
    + `.cursor/mcp.json` + camelCase hooks
  - `targets/copilot/build.py` — NEW; emits `plugin.json` +
    `.vscode/mcp.json` (with `servers` key, NOT `mcpServers`) +
    PascalCase hooks
  - `targets/antigravity/build.py` — NEW; emits `.agent/skills/`,
    `.agent/workflows/refine.md`, `mcp_config.json` snippet
  - `targets/claude-desktop/build.py` — polished; updated MCP launch
    to use entry-point scripts instead of file-path invocations
  - `targets/claude-code/build.py` — refactored to use shared helpers
    (behavior unchanged; cycle-4 tests still pass)
- **Per-target test suites** at `tests/targets/<name>/`, mirroring the
  cycle-4 pattern. ~6–8 tests per target × 6 targets ≈ 40 new tests.
- **Updated `docs/adding-targets.md`** with current host list, the
  stable target template, and a porting checklist.
- **`tools/build.py --all` verified** to build all 7 targets without
  conflict.

### What does NOT ship

- **Hermes target.** Not covered by the May 2026 research; the existing
  stub stays as-is. A future cycle can validate or remove it.
- **Auto-installer for scientific Python deps.** Cycle 5.
- **skill-refiner skill + the Stop hook scripts.** Cycle 6. Cycle-7
  builds emit a placeholder `/refine` command for hosts that support
  slash commands; hooks are NOT wired in cycle 7 (cycle 6 owns that).
- **Marketplace publishing / signed releases.** Future cycle.

### Primary use case

A developer wants ncplot-agent on their Codex CLI / Gemini CLI / Cursor
/ Copilot / Antigravity. They:

1. Clone the repo.
2. Run `python -m tools.build <target>`.
3. Follow the per-target install instructions in
   `build/<target>/ncplot-agent/README.md`.
4. The agent's skills + MCP tools become available.

Six hosts. One repo. One build step per target.

### Non-goals

- Not changing cycle 1/2 MCP server APIs.
- Not changing cycle 3 SKILL.md content. Skills are portable as-is.
- Not introducing new MCP tools.
- Not building per-host-specific skills (e.g., a "Cursor-only" skill).

---

## 2. Plugin payload structure (per target)

Each target produces `build/<target>/ncplot-agent/` with the host's
expected layout. The cores (skills + bundled MCP servers + plugin
README) are identical across targets; only the manifest, MCP launch
config, and command/hook formats differ.

### Common across all targets

- `skills/<name>/SKILL.md` — copy of cycle-3 skills (allowlist excludes
  `skill-refiner`)
- `mcp-servers/<name>/` — installable Python packages (re-rooted source
  + patched `pyproject.toml`)
- `README.md` — install + setup instructions

### Differs per target

| Target | Manifest path | MCP config path | MCP key | Command format | Hook config |
|--------|---------------|-----------------|---------|----------------|-------------|
| Claude Code | `.claude-plugin/plugin.json` | `.mcp.json` | `mcpServers` | `commands/<name>.md` | (cycle 6) |
| Codex CLI/Desktop | `.codex-plugin/plugin.json` | `config.toml` (TOML) | `[mcp_servers.X]` | (skills via `user-invocable`) | (cycle 6) |
| Gemini CLI | `gemini-extension.json` | `settings.json` | `mcpServers` | `commands/<name>.toml` | (cycle 6) |
| Cursor | `.cursor-plugin/plugin.json` | `.cursor/mcp.json` | `mcpServers` | `commands/<name>.md` | (cycle 6) |
| GitHub Copilot | `plugin.json` (root) | `.vscode/mcp.json` | `servers` ⚠ | `commands/<name>.md` | (cycle 6) |
| Antigravity | (no manifest needed) | `mcp_config.json` snippet | `mcpServers` | `.agent/workflows/<name>.md` | n/a |
| Claude Desktop | n/a (project doc concatenation) | `claude_desktop_config.json` snippet | `mcpServers` | n/a | n/a |

The Copilot `servers` vs `mcpServers` key is the one trap; everything
else is mechanical.

---

## 3. Shared helpers (`targets/_common/`)

### 3.1 `targets/_common/skills.py`

```python
INCLUDED_SKILLS = frozenset({
    "netcdf-inspect",
    "netcdf-plot-router",
    "netcdf-plot-map",
    "netcdf-plot-timeseries",
    "netcdf-plot-profile",
})

def copy_skills(src_root: Path, dst_skills_dir: Path) -> list[str]:
    """Copy cycle-3 skills (allowlist) into dst_skills_dir.
    Returns the list of skill names copied. Raises if any skill is missing."""
```

### 3.2 `targets/_common/mcp_bundling.py`

```python
MCP_SERVERS = [
    {"package_dir": "netcdf_reader", "external_name": "netcdf-reader",
     "entry_point": "ncplot-netcdf-reader"},
    {"package_dir": "plot_renderer", "external_name": "plot-renderer",
     "entry_point": "ncplot-plot-renderer"},
]

def bundle_mcp_servers(src_root: Path, dst_root: Path) -> list[dict]:
    """Re-root the MCP server source under dst_root/<name>/src/mcp/<name>/
    and patch pyproject.toml. Returns the list of server descriptors."""
```

These two helpers eliminate ~80 LOC of duplication per target.

### 3.3 `targets/_common/manifest.py`

```python
PLUGIN_NAME = "ncplot-agent"
PLUGIN_VERSION = "0.1.0"
PLUGIN_DESCRIPTION = (
    "Natural-language plotting from NetCDF files. Maps, time series, "
    "and vertical profiles. WRF/ROMS/CMIP/reanalysis aware."
)
PLUGIN_HOMEPAGE = "https://github.com/grnydawn/ncplot-agent"
PLUGIN_LICENSE = "MIT"

def common_ncplot_block(build_cycle: int) -> dict:
    return {
        "build_cycle": build_cycle,
        "ships_skills": sorted(INCLUDED_SKILLS),
        "ships_mcp_servers": [s["external_name"] for s in MCP_SERVERS],
    }
```

Each target's build.py consumes these constants and the helpers.
Per-target files become 50–100 LOC of host-specific glue.

---

## 4. Per-target build outputs

### 4.1 Codex CLI / Desktop (`targets/codex/`)

Output: `build/codex/ncplot-agent/`:

```
.codex-plugin/plugin.json    # manifest
skills/<name>/SKILL.md       # 5 skills
mcp-servers/<name>/          # bundled Python packages (entry-point scripts)
config.toml                  # TOML MCP launch stanzas
README.md
```

`config.toml` shape:
```toml
[mcp_servers.netcdf-reader]
type = "stdio"
command = "ncplot-netcdf-reader"
args = []

[mcp_servers.plot-renderer]
type = "stdio"
command = "ncplot-plot-renderer"
args = []
```

Slash command: cycle 7 ships **NO** custom slash command for Codex
because user-invocable slash commands aren't a confirmed Codex feature.
A skill marked `user-invocable: true` would surface as `/foo`, but
none of our cycle-3 skills have that frontmatter — adding it is a
cycle-3 SKILL.md change we explicitly avoid in cycle 7. Documented in
the README as a known gap.

### 4.2 Gemini CLI (`targets/gemini-cli/`)

Output: `build/gemini-cli/ncplot-agent/`:

```
gemini-extension.json        # extension manifest
skills/<name>/SKILL.md
mcp-servers/<name>/
settings.json                # MCP + (cycle-6: hooks)
commands/refine.toml         # /refine slash command
README.md
```

`gemini-extension.json` shape (per Gemini CLI docs):
```json
{
  "name": "ncplot-agent",
  "version": "0.1.0",
  "description": "...",
  "skills": "skills",
  "mcpServers": "settings.json#mcpServers",
  "commands": "commands"
}
```

`commands/refine.toml`:
```toml
description = "Review the current session and propose refinement drafts to the canonical skills. (Placeholder — full implementation in cycle 6.)"
prompt = "..."
```

### 4.3 Cursor (`targets/cursor/`)

Output: `build/cursor/ncplot-agent/`:

```
.cursor-plugin/plugin.json   # manifest
skills/<name>/SKILL.md
mcp-servers/<name>/
.cursor/mcp.json             # MCP launch stanzas
commands/refine.md           # /refine slash command
README.md
```

`.cursor/mcp.json` is structurally identical to Claude Code's
`.mcp.json`. Slash command frontmatter format is the same as Claude
Code's `commands/refine.md`.

Hooks: cycle-7 omits `.cursor/hooks.json` (cycle 6 will add it with
camelCase event names like `stop`).

### 4.4 GitHub Copilot (`targets/copilot/`)

Output: `build/copilot/ncplot-agent/`:

```
plugin.json                  # manifest at plugin root (NOT in subdirectory)
skills/<name>/SKILL.md
mcp-servers/<name>/
.vscode/mcp.json             # MCP — note: "servers" key, not "mcpServers"
commands/refine.md           # slash command
README.md
```

⚠ **Pitfall:** `.vscode/mcp.json` uses `{"servers": {...}}` instead of
`{"mcpServers": {...}}`. The build emits the correct key; the test
suite asserts on it.

Hooks: deferred to cycle 6.

### 4.5 Antigravity (`targets/antigravity/`)

Output: `build/antigravity/ncplot-agent/`:

```
.agent/
├── skills/<name>/SKILL.md   # project-scope skills location
└── workflows/refine.md      # /refine workflow (markdown body, not just frontmatter)
mcp-servers/<name>/
mcp_config.json              # snippet user pastes into Antigravity's MCP config
README.md
```

No top-level manifest — Antigravity discovers skills + workflows by
their directory location. The README documents how the user pastes
`mcp_config.json` contents into the Antigravity MCP-config UI.

Hooks: not available in Antigravity — cycle-6 self-improvement degrades
to a manual `/refine` workflow invocation. Documented in this target's
README as a known limitation.

### 4.6 Claude Desktop polish (`targets/claude-desktop/`)

The existing stub (pre-cycle-4) concatenates skill bodies into a
project instructions document and emits an MCP config snippet. Cycle-7
polish:
- Update the MCP snippet to use entry-point scripts
  (`ncplot-netcdf-reader`, `ncplot-plot-renderer`) instead of
  `python <path>/server.py` invocations
- Bundle MCP servers under `mcp-servers/` (same re-rooted layout as
  cycles 4+7) so users can `pip install` from the build artifact
- Refactor build.py to use the shared helpers
- Add a test suite

Slash commands and hooks: still unavailable in Claude Desktop. The
`/refine` flow degrades to "manually invoke the refiner skill from
your project doc."

### 4.7 Claude Code refactor (`targets/claude-code/`)

The cycle-4 build.py is rewritten to consume `targets/_common/`
helpers. Behavior identical; cycle-4 test suite passes unchanged.

---

## 5. Tests

### 5.1 Per-target test suites

For each new/refactored target, a `tests/targets/<name>/` dir with
~6–8 tests:

- `test_build_runs.py` — top-level dirs/files present, build idempotent
- `test_manifest_schema.py` (or `test_extension_schema.py` for Gemini,
  `test_no_manifest.py` for Antigravity / Claude Desktop) — host-specific
  manifest shape
- `test_skills_copied.py` — 5 cycle-3 skills present, refiner absent
- `test_mcp_servers_bundled.py` — re-rooted source + patched pyproject
  (shared with cycle 4)
- `test_mcp_config.py` — host-specific MCP config shape
- `test_commands.py` (where applicable) — `/refine` placeholder present
- `test_no_hooks.py` — cycle-6 deferral

The `built_plugin` fixture pattern from cycle 4 carries over; each
target's `conftest.py` invokes its own build.py.

### 5.2 Shared-helper tests

`tests/targets/_common/test_skills.py` — `copy_skills()` allowlist
correctness.

`tests/targets/_common/test_mcp_bundling.py` — `bundle_mcp_servers()`
re-roots correctly.

These tests are run independently of any specific target build.

### 5.3 Cross-target tests

`tests/targets/test_all_targets_buildable.py` — invokes `tools/build.py
--all` in a tmp dir, asserts all 7 targets produce non-empty
`ncplot-agent/` directories.

This is a smoke test for the dispatcher; per-target validity is
covered by the host-specific suites.

### 5.4 What we don't test

- Plugin loading inside the actual host. Manual integration tests
  documented in the PR body.
- MCP servers running over stdio. Cycle 1/2 tests cover this.
- Hot-reload, version upgrades. Future cycles.

---

## 6. Build dispatcher updates

`tools/build.py` keeps its current shape but the `--list` output now
shows 8 targets (claude-code, claude-desktop, codex, cursor, gemini-cli,
copilot, antigravity, hermes). `--all` builds everything in sorted
order. `--validate <target>` runs that target's test suite.

No new flags for cycle 7. The infrastructure was already in place.

---

## 7. Documentation

### 7.1 `docs/adding-targets.md`

Updated to:
- List all 7+1 hosts with current research-backed status
- Show the standard build.py skeleton using `targets/_common/` helpers
- Document the per-host idiosyncrasies (Copilot's `servers` key,
  Antigravity's lack of hooks, Claude Desktop's no-skill-loader)

### 7.2 Per-target READMEs

Each `targets/<name>/README.md` describes:
- How to run the build
- What the build produces
- Per-host install instructions (where to copy, what config to merge)
- Known limitations (hooks unavailable / slash commands degraded /
  manual integration steps)

### 7.3 `targets/<name>/build/<name>/ncplot-agent/README.md`

Each build artifact also generates an end-user README inside the plugin
payload, with host-specific install instructions.

---

## 8. Open risks

### 8.1 Host plugin format drift

**Risk:** Codex / Gemini CLI / etc. change their plugin manifest
schema between now and merge.

**Response:** Per-target `test_manifest_schema.py` pins the expected
shape. Each new target ships with the schema-as-of-build.

### 8.2 Slash-command authoring uncertainty

**Risk:** Codex's custom slash-command file format is unconfirmed in
official docs. Adding `user-invocable: true` to skills is a cycle-3
change we want to avoid.

**Response:** Codex target ships without a custom `/refine` command
(documented as a known gap in the target README). When Codex
publishes a clear authoring format, a small follow-up cycle adds it.

### 8.3 Antigravity hooks

**Risk:** Antigravity may add hooks before cycle 6 ships skill-refiner,
making the cycle-6 no-hook degradation unnecessary.

**Response:** Cycle 6 will check Antigravity hook support at that
time. Cycle 7 ships the manual-workflow degradation; cycle 6 can
upgrade if hooks become available.

### 8.4 Copilot `servers` key

**Risk:** A reader of `targets/copilot/build.py` copies the pattern
to a future target and writes `servers` instead of `mcpServers`.

**Response:** A comment in the build.py near the key write explains
why Copilot is different. The test suite asserts on the correct key
per target.

### 8.5 Claude Code refactor regression

**Risk:** Refactoring cycle-4's `targets/claude-code/build.py` to use
shared helpers introduces a behavior change.

**Response:** Cycle-4 tests run unchanged. Any regression fails the
existing suite immediately.

### 8.6 `--all` build conflicts

**Risk:** Two targets write to the same path and clobber each other.

**Response:** Each target writes to `build/<target>/`, isolated by
target name. `tools/build.py` enforces this. Test
`test_all_targets_buildable.py` confirms.

### 8.7 Reference-data duplication

**Risk:** The `references/` subdirs (regions.json, colormaps.json,
etc.) are 5–10 KB each, multiplied across 6 build artifacts ≈ 50 KB
duplication.

**Response:** Acceptable. The data is part of the skill payload; each
host needs its own copy. Future cycle could centralize by symlink in
the build, but that's premature.

---

## 9. Cross-cutting principles

### 9.1 Inherited from cycles 1–4

1. **TDD per task.**
2. **Atomic commits.**
3. **No silent fallback.** Hosts that don't support a feature get a
   documented degradation, not a fake.
4. **Build is idempotent.** Each `python -m tools.build <target>`
   wipes and re-emits the artifact.
5. **No build artifact in version control.** `build/` gitignored.

### 9.2 New for cycle 7

6. **Shared helpers in `targets/_common/`.** Per-target build.py
   files are thin glue; the heavy lifting (MCP bundling, skills copy,
   manifest constants) lives in one place.
7. **Skill-refiner + Stop hook stay deferred.** Cycle 7 ships the
   placeholder `/refine` command (where supported); cycle 6 wires up
   the closed loop.
8. **Per-host gaps are explicit.** Each target README documents what
   degrades on that host (Antigravity: no hooks; Codex: no custom
   slash; Claude Desktop: no skill loader).
9. **`servers` vs `mcpServers` is host-specific data, not magic.** The
   key name is set in the build.py for each target; a single `_common`
   helper would have to special-case Copilot, which would obscure
   rather than clarify. Keep the key in each per-target file with a
   comment.

### 9.3 What cycle 7 does NOT establish

- A signed release format
- A marketplace listing for any host
- A plugin update mechanism
- Hermes target validation

---

## End of spec

Implementation plan goes in
`docs/plans/2026-05-08-cycle-7-multi-host-targets.md`.

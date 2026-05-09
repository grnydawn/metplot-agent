# Cycle 6 dogfood findings

> Phase A of cycle 6 (see `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md`).
> Format and category definitions: `docs/dogfood-tester-guide.md`.

Sessions: 2   Time invested: 10 min
Files exercised:
- `.scratch/synthetic_tas.nc` (synthetic monthly-mean tas, 2024, 73×144 grid, CF-1.7) — sanity check (c) only

## alias

(no findings yet)

## region

(no findings yet)

## pitfall

(no findings yet)

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

# Cycle 6 dogfood findings

> Phase A of cycle 6 (see `docs/specs/2026-05-08-cycle-6-self-improvement-loop.md`).
> Format and category definitions: `docs/dogfood-tester-guide.md`.

Sessions: 1   Time invested: 5 min
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

### MCP tools not registered to agent on first session after install (session-start race)
- **Date:** 2026-05-09
- **Scenario:** Sanity check (c) — first session after fresh `/plugin install` + `/metplot:setup` + restart. Asked the agent: "Inspect the NetCDF file at `.scratch/synthetic_tas.nc`."
- **Plugin behavior:** The `metplot:netcdf-inspect` skill activated. The skill says "Call `netcdf-reader.inspect(path=...)`." But the MCP tool was **not present in the agent's tool surface** — `ToolSearch` queries for `netcdf`, `metplot`, `inspect` all returned "No matching deferred tools." The agent could not invoke the MCP tool through normal channels and had to bypass via direct JSON-RPC handshake to the launcher to fulfill the request.
- **Diagnosis:** `claude mcp list` reported both `netcdf-reader` and `plot-renderer` as ✓ Connected, and a direct stdio JSON-RPC handshake to the launcher returned all 8 tools (`inspect`, `resolve_spec`, `regrid_to_centers`, `peek`, `read_slice`, `compute_stats`, `find_variables`, `find_time`) and a correct inspect result. So the server is healthy and reachable. The agent's tool surface was finalized before the MCP server's tool advertisement reached it. Likely a race: SessionStart hook ran `setup.sh --quiet` which spent several seconds on `cartopy`/`scipy` installs, while Claude Code's agent-tool registration ran in parallel and committed before the MCP servers were ready.
- **Confidence:** medium. Reproduced once on first restart-after-install. Need to confirm whether the second restart fixes it (setup is idempotent and finishes in ~1s when packages are already present, so MCP servers should come up before the agent surface finalizes on subsequent restarts).
- **Should the loop have remembered:** no — this isn't a refinement target. The refiner edits skill files; this is install-pipeline behavior. Belongs in cycle-6 spec discussion or a separate install-flow ticket.
- **Why this matters for dogfood:** A real Phase A scenario (any plot/inspect request) would fail on first-session-after-install with "I don't have access to that tool." The user-visible install flow looks successful (`Setup complete. 4/4 succeeded`, `claude mcp list` shows Connected) but the agent's view differs. Either the install flow needs to gate on MCP-tool registration, or the dogfood guide needs to warn testers that a second restart is required.

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

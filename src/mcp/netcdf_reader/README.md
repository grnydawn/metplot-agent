# netcdf-reader MCP

MCP server for inspecting and reading NetCDF data. Implements the
cycle-1 surface defined in `docs/specs/2026-05-06-cycle-1-netcdf-reader.md`.

## Tools

| Tool | Group | Purpose |
|------|-------|---------|
| `inspect(path)` | D-path | Metadata summary; cached |
| `resolve_spec(path, variable, ...)` | D-path | Validate selectors → normalized spec |
| `regrid_to_centers(spec)` | D-path | Annotate U/V/W destaggering on a spec |
| `peek(path, variable, ...)` | C-path | Single-point lookup; ≤10 KB hard cap |
| `read_slice(path, variable, ..., max_inline_bytes)` | C-path | Inline (<100 KB default) or session-temp file |
| `compute_stats(path, variable, ...)` | C-path | min/max/mean/std/percentiles 5/50/95 |
| `find_variables(path, hint)` | help | Score variables by long_name/standard_name/etc. |
| `find_time(path, hint)` | help | Parse "first"/"last"/ISO partials |

## Path schemes

| Scheme | How |
|--------|-----|
| `file` (or bare path) | xarray |
| glob (`/data/*.nc`), directory | `open_mfdataset` with combine fallback |
| `https://` / `http://` | OPeNDAP via xarray + netCDF4 (curl support) |
| `s3://` | requires `s3fs` |
| `ssh://[user@]host[:port]/path` | paramiko SFTP → h5netcdf engine |

## Response envelope

Every tool returns one of:

```json
// success
{"ok": true, "result": {...}, "warnings": [...], "resolved": {...}}

// terminal error
{"ok": false, "error": {"code": "<error_code>", "message": "...", "context": {...}}, "warnings": [...]}

// ambiguity (skill should ask the user)
{"ok": false, "error": {"code": "ambiguous", "subcode": "...", "candidates": [...], "prompt": "...", "retry_with_param": "..."}, "warnings": []}
```

See `envelope.py` for the full error/warning code taxonomy.

## SSH credential flow

Silent auth chain: `~/.ssh/config` → ssh-agent → default identity files.
On exhaustion, returns `ambiguous + ssh_auth_needed` with candidate
methods. Caller retries with `ssh_config={"user": ..., "host": ...,
"auth": {"method": "password|identity_file", ...}}`. Credentials live
in process memory only, never written to disk.

## Install

```bash
pip install -e 'src/mcp/netcdf-reader[dev]'
# Optional extras:
pip install -e 'src/mcp/netcdf-reader[remote]'  # s3fs
pip install -e 'src/mcp/netcdf-reader[wrf]'     # xwrf for WRF transforms
pip install -e 'src/mcp/netcdf-reader[roms]'    # xroms for ROMS transforms
```

## Run

```bash
metplot-netcdf-reader   # via stdio MCP transport
```

Or wire from a Claude Code plugin manifest (cycle 4).

## Cache locations

- `.metplot/inspections/<hash>.json` — persistent inspection cache (mtime-keyed)
- `.metplot/slices/<session>/...` — session-scoped slice temp files (cleared at startup)

## Testing

```bash
pytest tests/mcp/netcdf-reader/unit/ -v          # synthetic fixtures, fast
NCPLOT_INTEGRATION=1 pytest tests/mcp/netcdf-reader/integration/ -m integration
NCPLOT_REAL_SSH=1 pytest tests/mcp/netcdf-reader/integration/ -m real_ssh
```

See `tests/mcp/netcdf-reader/REAL_SSH_SETUP.md` for real-SSH test setup.

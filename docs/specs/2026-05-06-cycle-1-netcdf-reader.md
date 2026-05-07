# Cycle 1: `netcdf-reader` MCP — Design

**Status:** Approved (brainstorm complete)
**Date:** 2026-05-06
**Scope:** Cycle 1 of 6. The full project decomposition is:

1. **`netcdf-reader` MCP** ← this doc
2. `plot-renderer` MCP
3. Plot skills bundle (`netcdf-inspect`, `netcdf-plot-router`, `netcdf-plot-{map,timeseries,profile}`)
4. Claude Code target builder (`targets/claude-code/`)
5. Semi-auto setup (dependency detection + install offers for `xarray`, `netCDF4`, `cartopy`, `paramiko`, etc.)
6. `skill-refiner` + task-log schema + `apply_refinements.py` review CLI

Targets other than Claude Code (Desktop, Codex, Hermes) remain as scaffold stubs in `targets/` and are out of scope for cycles 1–6. The architecture stays untouched so they can be wired up later.

---

## 1. Overview

The `netcdf-reader` is one of two foundation MCP servers (the other is `plot-renderer`, cycle 2). Its job is to expose NetCDF data to AI agents in a way that:

- Avoids loading large arrays into the agent's context
- Handles the heterogeneity of real-world NetCDF (CF, WRF, ROMS, CMIP)
- Supports local single files, local multi-file globs, remote URLs (OPeNDAP / S3), and SSH-served files
- Surfaces structured ambiguity rather than silently guessing
- Is usable as a standalone MCP outside the ncplot skills

### Primary use cases

- **B-tier (primary):** WRF / ROMS / CESM regional model output — typically 10–100 GB per file, often multi-file (one file per time chunk), staggered grids common
- **A-tier (secondary):** CF-compliant climate model output (CMIP-style) — usually < 5 GB per file
- **C-tier (secondary):** Reanalysis (ERA5, MERRA-2) — multi-file by year/month/variable

### Out of scope (cycle 1)

- Zarr / GRIB / HDF5 readers (planned as separate MCPs in future cycles; see §11 for the seam)
- Heavyweight WRF/ROMS transforms: eta→pressure (WRF), sigma→z (ROMS), pressure-coord cross-sections — punted to optional `xwrf` / `xroms` deps; cycle 5 wires the install offer
- SSH transport variants beyond SFTP streaming: stage-and-cache, sshfs auto-mount, remote execution
- Slice-cache dedup, stats cache, slice-cache size cap (deferred per YAGNI)
- Performance benchmarks, dask cluster scheduling, parallel `open_mfdataset`
- Variable-write / derived-variable persistence (reader is read-only)
- Auth beyond SSH (no HTTP basic auth, no OAuth, no AWS IAM beyond what `s3fs` provides)
- Schema-evolution / backwards compatibility for the response envelope (v1 only; rev after cycle 6)
- `skill-refiner` integration (cycle 6)
- Localization

---

## 2. Tool surface

Nine callable tools, three logical groups.

### Plotting path (D-path) — no array data crosses the agent

| Tool | Purpose |
|------|---------|
| `inspect(path)` | Metadata summary of a file or multi-file dataset; cached |
| `resolve_spec(path, variable, *, time, level, lat, lon, region, regrid)` | Validate & normalize a slice spec; never reads array values |
| `regrid_to_centers(spec)` | Annotate a spec with U/V/W destaggering; pure spec transform |

The `plot-renderer` (cycle 2) consumes `(path, spec)` and re-opens the source with dask at render time. No data marshalling between MCPs for plotting traffic.

### Analysis path (C-path) — data crosses the agent, sized appropriately

| Tool | Purpose |
|------|---------|
| `peek(path, variable, *, time, level, lat, lon)` | Single-point or tiny-area lookup; always inline; hard-capped at 10 KB |
| `read_slice(path, variable, *, ..., max_inline_bytes=100_000)` | Hybrid: inline JSON if ≤ threshold, else session-scoped temp file |
| `compute_stats(path, variable, *, ...)` | Cheap summary stats (min/max/mean/std/count/fraction_nan/p5/p50/p95); always inline |

### Help path (hint-based; standalone-MCP usability)

| Tool | Purpose |
|------|---------|
| `find_variables(path, hint)` | Score variables against `long_name`/`standard_name`/`description` attrs |
| `find_time(path, hint)` | Parse common forms ("2024-09", "last", "first") into ISO + index |

Plus an **implicit lifecycle hook** — not a callable tool — that on MCP server shutdown closes SSH connections, zeroes credentials, and removes the session's slice temp directory.

---

## 3. Architecture: D-path / C-path split

The reader has one MCP server but two flows, picked by the consumer.

**D-path (plotting):** Skills call `inspect` + `resolve_spec` to get a normalized slice spec. The renderer (cycle 2) re-opens the source path at render time with dask, applies the spec's selectors and transforms, renders, and saves the figure. **No array data ever crosses the agent or any MCP boundary.** Works for files of any size.

**C-path (analysis):** When the user asks data questions (point values, regional aggregates, custom analysis), the agent needs actual numbers. `peek` always returns inline (small). `read_slice` returns inline JSON below `max_inline_bytes` and a session-scoped temp file path above it. `compute_stats` returns aggregates only.

Why this split: a single "always return data" reader either limits scope sharply (refuse big slices) or balloons context (return huge JSON). The split lets plotting handle arbitrary file sizes while keeping analysis responsive for the small-data case.

---

## 4. Convention detection and normalization

`inspect()` runs convention detection eagerly. Other tools rely on the cached result.

### Detection signals (in order)

1. **Global attrs.** `Conventions: "CF-1.x"` → CF; `TITLE` containing "OUTPUT FROM WRF" or `MMINLU` → WRF; `s_rho`/`s_w`/`Cs_r` → ROMS; `cmor_version`/`mip_era` → CMIP.
2. **Dim/coord shape.** `west_east_stag` / `south_north_stag` / `bottom_top_stag` → WRF; `lat_rho`/`lon_rho` 2D → ROMS curvilinear.
3. **Variable names.** `Times` (string array) → WRF; `ocean_time` → ROMS.

### Reported in `inspect()` output

```json
{
  "convention": {
    "primary": "WRF",
    "confidence": "high",
    "evidence": ["TITLE attr matches OUTPUT FROM WRF", "west_east_stag dim present"],
    "candidates": null
  }
}
```

When confidence is **low** or signals conflict:

```json
"candidates": [
  {"convention": "WRF", "confidence": 0.6, "evidence": [...]},
  {"convention": "CF-generic-staggered", "confidence": 0.4, "evidence": [...]}
],
"prompt": "This file looks like WRF output with CF metadata, or a generic CF file with staggered grids. Which?"
```

Skills surface this as a multiple-choice question to the user (the **"ask when ambiguous, never silently guess"** cross-cutting principle).

### Normalization done inline

- **Time decoding.** WRF `Times` (byte-string array) → CF `datetime64`. ROMS `ocean_time` already CF-compatible.
- **Longitude convention reporting.** `inspect()` reports `lon_convention: "0..360" | "-180..180" | "mixed"`. Reader does **not** auto-shift; the renderer applies the shift based on the requested region.
- **Basic destaggering.** `regrid_to_centers` annotates a spec with `(da[1:] + da[:-1]) / 2` along the staggered dim. Lazy.
- **2D curvilinear coord recognition.** `inspect()` reports `coord_kind: "rectilinear" | "curvilinear" | "unstructured"`.

### Punted to optional `xwrf` / `xroms`

- WRF eta → pressure / height interpolation
- ROMS sigma → z interpolation with bathymetry + sea-surface height
- Pressure-coord / height-coord cross-sections for these models

When a tool call needs a punted transform, reader returns `convention_transform_unavailable` with a hint to install `xwrf` / `xroms`. Cycle 5 (semi-auto setup) wires the install offer.

---

## 5. Selector grammar

All data tools (`resolve_spec`, `read_slice`, `compute_stats`, `peek`) accept the same canonical selector grammar. Skills do natural-language translation; reader does deterministic resolution.

### `time`

One of:

- ISO string: `"2024-09"`, `"2024-09-15"`, `"2024-09-15T12:00"`
- Range: `["2024-01", "2024-12"]` (inclusive)
- Index: `{index: 5}` or `{index: [0, 6, 12]}`
- Sentinel: `"first"` | `"last"`

If the value doesn't match exactly, reader returns candidates (nearest available times with their distance) — does not silently snap.

### `level`

One of:

- Numeric: `500` (in the file's native unit; `inspect()` reports the unit)
- List: `[500, 850, 1000]`
- Index: `{index: 0}` or `{index: [0, 5, 10]}`
- Sentinel: `"surface"` | `"top"` (resolved using the vertical coord's monotonic direction)

If the variable has no level dim, `level` is rejected with `not_4d`.

### `lat` / `lon`

One of:

- Bounding box: `lat=[20, 70]`, `lon=[-80, 0]`
- Single point: `lat=42.3`, `lon=-71.0` (scalars trigger nearest-neighbor with reported distance)
- Slice indices: `{index: [0, 100]}`

For curvilinear grids (WRF/ROMS 2D coords), the reader uses xarray's `.where()` masking on the 2D coord arrays.

### `region`

String name. The reader does **not** resolve regions itself. Skills look up `region` in `src/data/regions.json` and pass `lat`/`lon` to the reader.

### `variable`

Exact name from `inspect()`'s variable list. No fuzzy matching. If the name doesn't match, reader returns the top-3 closest matches by string distance + `find_variables(path, variable)` results.

### `regrid`

Optional. One of `"to_centers"` (cycle 1's only supported value) or omitted.

### Cross-cutting: every selector returns the resolved value

If `time="2024-09"` matches `"2024-09-16T00:00:00"`, the response includes `resolved_time: "2024-09-16T00:00:00"` and `time_match: "nearest, distance=15 days"`. Skills can echo this back to the user.

---

## 6. Path handling

Tool inputs accept a single string `path`. Reader classifies into one of four kinds.

### Local single file

Bare path or `file://` URL. Default case. Opens with `xarray.open_dataset(path, decode_times=True, chunks="auto")`.

### Local multi-file

Glob (`/data/wrf/wrfout_d01_2024-*`) or directory. Reader expands the glob, sorts deterministically, opens with `xarray.open_mfdataset(files, combine="by_coords", parallel=False)`. Cache key is `sha256(sorted_files + mtimes)`.

If `combine="by_coords"` fails, reader retries with `combine="nested"` along the most likely concat dim (heuristic: shared `time` dim with non-overlapping ranges → concat on `time`). If both fail, returns `multi_file_combine_failed` with the conflict description.

### Remote URL

`http://`, `https://` (OPeNDAP / Thredds), `s3://`. Pass-through to `xarray.open_dataset` (xarray + netCDF4 with curl support handles OPeNDAP; `s3://` needs `s3fs`). Cache key for remote is URL-only (no mtime check) with documented caveat.

### SSH remote

`ssh://[user@]host[:port]/path/to/file.nc`. See §7 for the full credential flow. Implementation: paramiko opens an SFTP client; `xarray.open_dataset(file_like, engine="h5netcdf")` reads through it. (`netCDF4` engine doesn't accept file-like objects; `h5netcdf` does.)

### Path-classification edge cases

- Mixed `ssh://` + glob: supported (one SFTP connection, multiple file handles)
- Mixed local + remote in one glob: rejected with `unsupported_path_scheme`
- Symlinks: followed; cache key uses the resolved real path

### Honest caveat

For SSH-streamed reads of B-tier files (10–100 GB), the reader emits a `slow_remote_read` warning when a single tool call exceeds 30 s, suggesting either staging via SFTP or sshfs. Cycle 1 doesn't implement staging or sshfs — just streams and warns.

---

## 7. SSH credential-prompt flow

### Path scheme

```
ssh://[user@]host[:port]/absolute/path/to/file.nc
```

`host` may be a hostname OR a `~/.ssh/config` alias.

### Connection-resolution chain

When a tool call references an `ssh://` path, reader tries auth methods in order. **Each attempt is silent (no prompt)** — only if every silent method fails does the reader return a structured prompt.

1. **`~/.ssh/config` lookup.** If `host` matches an alias, extract `HostName`, `Port`, `User`, `IdentityFile`, `ProxyJump` as defaults.
2. **ssh-agent.** If `SSH_AUTH_SOCK` is set, try its keys.
3. **Default identity files.** `~/.ssh/id_ed25519`, `~/.ssh/id_rsa`, `~/.ssh/id_ecdsa` (in that order).
4. **If all fail → return `ssh_auth_needed`** (see envelope §9).

This means users with a sane `~/.ssh/config` + ssh-agent setup never see an auth prompt.

### `ssh_auth_needed` response shape

```json
{
  "ok": false,
  "error": {
    "code": "ambiguous",
    "subcode": "ssh_auth_needed",
    "session_id": "ssh-abc123",
    "message": "SSH authentication needed for youngsung@hpc.example.org",
    "context": {
      "host": "hpc.example.org",
      "port": 22,
      "user": "youngsung",
      "tried": [
        {"method": "ssh_config", "result": "no matching alias"},
        {"method": "ssh_agent", "result": "no keys offered"},
        {"method": "default_identity_files", "result": "~/.ssh/id_ed25519 rejected"}
      ],
      "may_need_jump_host": false
    },
    "candidates": [
      {"value": "identity_file", "label": "Path to a private key file",
       "param": "identity_file", "sensitive": false},
      {"value": "password", "label": "Password (in-memory only, not stored)",
       "param": "password", "sensitive": true},
      {"value": "ssh_config_alias", "label": "Use a different ~/.ssh/config alias",
       "param": "ssh_alias", "sensitive": false}
    ],
    "retry_with_param": "ssh_config",
    "prompt": "SSH auth needed for youngsung@hpc.example.org. ssh-agent and default keys didn't work. How would you like to authenticate?"
  }
}
```

### Retry with structured `ssh_config`

```python
read_slice(
    path="ssh://hpc.example.org/data/wrf.nc",
    variable="t2m",
    ssh_config={
        "user": "youngsung",
        "host": "hpc.example.org",
        "port": 22,
        "auth": {"method": "password", "password": "<redacted>"},
        "session_id": "ssh-abc123"
    }
)
```

### Session-scoped connection pool

- Keyed by `(user, host, port)` for the lifetime of the MCP server process
- First successful auth opens a paramiko `Transport` + `SFTPClient`; stored keyed by `session_id`
- Subsequent calls reference by `session_id` (no re-auth)
- If a connection drops mid-session, reader silently reconnects once using cached credentials before re-prompting
- On MCP shutdown: connections close, credentials zeroed
- Credentials live **only in process memory**: never written to `.ncplot/`, never logged, never echoed in tool output

### Multi-step auth (2FA, encrypted keys, keyboard-interactive)

After a password submission, if the server demands 2FA, the next response is:

```json
{
  "ok": false,
  "error": {
    "code": "ambiguous",
    "subcode": "ssh_auth_needed",
    "session_id": "ssh-abc123",
    "step": 2,
    "previous_method": "password",
    "context": {"remote_prompt": "Enter Duo passcode or 'push':"},
    "candidates": [
      {"value": "interactive_response", "label": "Enter Duo passcode or 'push'",
       "param": "response", "sensitive": true}
    ]
  }
}
```

For encrypted private keys, reader detects the passphrase requirement and emits an `interactive_response` candidate with `sensitive: true`.

### Jump host (bastion / `ProxyJump`)

If the direct connection is refused and `~/.ssh/config` shows a `ProxyJump`, reader chains transports automatically (paramiko's `sock=` parameter).

If the user manually specifies a jump host:

```python
ssh_config={
    "user": "youngsung", "host": "internal.hpc.org",
    "jump": {"user": "youngsung", "host": "bastion.example.org", "port": 22}
}
```

If the jump host itself needs auth, the credential-prompt flow recurses; each step gets its own `step` field.

### Security guarantees

- Passwords / passphrases / OTP responses **never written to disk**
- **No keychain integration** in cycle 1 (users on macOS who want it use ssh-agent + Keychain integration that already exists at the OS level)
- **Sensitive fields tagged** so the agent UI can redact (`sensitive: true`)
- **No credential serialization** in cache files, logs, or `.ncplot/inspections/`
- **`session_id` is opaque** — does not encode credentials, just references the in-memory pool
- **No re-prompt across MCP restarts** — fresh process means fresh prompts (most secure default)

### Cycle-5 install impact

Adds one Python dep: **`paramiko`**. No system packages. Cycle 5's setup helper detects it as missing and offers to install.

---

## 8. Caching

### Inspection cache (`.ncplot/inspections/<hash>.json`)

- Hash key: `sha256(canonical_path + mtime + size)` for local files; `sha256(sorted_file_list + mtimes)` for multi-file; `sha256(url)` for remote (URL-only, with documented stale-data caveat)
- On every `inspect()` call: stat the file(s) first, recompute hash, compare to cache. Mismatch → invalidate and re-read
- Cache entry is plain JSON, human-readable, hand-deletable
- No TTL, no auto-cleanup. Cache is small (KB per file) and survives indefinitely

### Slice temp files (`.ncplot/slices/<session_id>/`)

- Created by C-path `read_slice` only when output exceeds `max_inline_bytes`
- `session_id` = MCP server process ID + start time (opaque to the agent; included in tool responses)
- Directory created lazily on first overflow
- **Cleaned at MCP server startup** (the previous session's directory is removed). Slice temp files don't survive across sessions
- No size cap in cycle 1; if disk fills up, that's a real-world signal and we add a cap later

### Not cached

`compute_stats`, `peek`, `resolve_spec` — each call recomputes. Cheap (lazy/dask reads of metadata or summary aggregates); marginal benefit doesn't justify staleness risk.

### SSH connection pool

Technically a cache: keyed by `(user, host, port)`, lives only in process memory, torn down on MCP shutdown. Already covered in §7.

---

## 9. Response envelope

Every tool returns the same outer shape so skills can handle them uniformly. **MCP itself doesn't standardize a success/error envelope** — this is a convention we enforce inside the reader. Documented in `src/mcp/netcdf-reader/README.md`.

### Success envelope

```json
{
  "ok": true,
  "result": { /* tool-specific payload */ },
  "warnings": [
    {"code": "slow_remote_read", "message": "...", "context": {...}}
  ],
  "resolved": { /* echoed normalized inputs (resolved time, applied lon shift, etc.) */ }
}
```

### Error envelope (terminal failure, no candidates)

```json
{
  "ok": false,
  "error": {
    "code": "remote_file_not_found",
    "message": "Path /data/wrf.nc does not exist on hpc.example.org",
    "context": {"host": "...", "path": "..."}
  },
  "warnings": [...]
}
```

### Ambiguity envelope (skill should ask the user)

```json
{
  "ok": false,
  "error": {
    "code": "ambiguous",
    "subcode": "convention" | "variable" | "ssh_auth_needed" | "time_match" | "region" | "multi_file_combine",
    "message": "Human-readable description",
    "candidates": [
      {"value": "...", "label": "...", "evidence": [...], "confidence": 0.7,
       "param": "...", "sensitive": false}
    ],
    "prompt": "Suggested user-facing question",
    "retry_with_param": "convention" | "variable" | "ssh_config" | "...",
    "context": {...}
  }
}
```

### Error code taxonomy (cycle 1)

```
file_not_found                       — local path doesn't exist
remote_file_not_found                — SSH/HTTP path doesn't exist
remote_permission_denied             — file exists but unreadable
multi_file_combine_failed            — open_mfdataset couldn't merge
unsupported_path_scheme              — e.g., ftp://
ssh_auth_failed                      — wrong creds; retry with new ones
ssh_timeout                          — network unreachable
unknown_variable                     — variable name not in file (use find_variables)
out_of_bounds                        — selector falls outside coord range
empty_slice                          — selector resolves to zero elements
size_limit_exceeded                  — peek/inline exceeded the inline cap
convention_transform_unavailable     — needs xwrf/xroms; cycle-5 install hint
not_4d                               — `level` requested on non-4D variable
internal_error                       — uncaught exception with traceback in context
ambiguous                            — see subcode for which kind
```

### Warning code taxonomy

```
slow_remote_read                     — > 30s for one call
high_nan_fraction                    — > 50% NaN in resolved slice
constant_field                       — min == max
non_monotonic_coord                  — coord axis not strictly monotonic
non_standard_calendar                — cftime fallback used
percentile_clip_suggested            — extreme outliers detected
```

### Why this envelope

The agent's tool-result handling becomes a tight pattern:

1. Check `ok`
2. If `false` and `error.code == "ambiguous"`, surface `candidates` + `prompt` to the user
3. If `false` and not ambiguous, surface the error message
4. If `true`, proceed and append any `warnings` to the user-facing reply

Skills don't need bespoke parsing per tool.

---

## 10. Tool output schemas

Schemas live inside `result` of the success envelope.

### `inspect(path)`

```json
{
  "path": "/data/wrf.nc",
  "kind": "local_single",
  "files": ["/data/wrf.nc"],
  "convention": {
    "primary": "WRF",
    "confidence": "high",
    "evidence": ["TITLE attr matches OUTPUT FROM WRF"],
    "candidates": null
  },
  "variables": [
    {"name": "T2", "long_name": "Temperature at 2m", "standard_name": null,
     "units": "K", "dims": ["Time", "south_north", "west_east"],
     "shape": [13, 290, 200], "dtype": "float32",
     "grid_kind": "scalar", "is_staggered": false},
    {"name": "U", "long_name": "x-wind component",
     "dims": ["Time", "bottom_top", "south_north", "west_east_stag"],
     "shape": [13, 33, 290, 201], "grid_kind": "U", "is_staggered": true}
  ],
  "time": {"name": "Time", "calendar": "standard",
           "range": ["2024-09-01T00:00", "2024-09-01T12:00"],
           "step": "PT1H", "n": 13, "monotonic": "increasing"},
  "spatial": {"coord_kind": "curvilinear",
              "lat_name": "XLAT", "lon_name": "XLONG",
              "lat_range": [25.1, 50.4], "lon_range": [-130.2, -90.1],
              "lon_convention": "-180..180"},
  "vertical": {"name": "bottom_top", "kind": "eta",
               "units": "1", "n": 33, "monotonic": "decreasing"},
  "dims": {"Time": 13, "bottom_top": 33, "south_north": 290, "west_east": 200,
           "west_east_stag": 201, "south_north_stag": 291, "bottom_top_stag": 34},
  "attrs": {"TITLE": "OUTPUT FROM WRF V4.5", "GRIDTYPE": "C"}
}
```

### `resolve_spec(...)`

```json
{
  "path": "/data/wrf.nc", "variable": "T2",
  "selectors": {"time": "2024-09-01T12", "lat": [40, 45], "lon": [-100, -90]},
  "resolved": {
    "time_value": "2024-09-01T12:00:00", "time_index": 12, "time_match": "exact",
    "lat_indices": [120, 175], "lon_indices": [88, 142]
  },
  "slice_shape": [1, 56, 55],
  "estimated_bytes": 12320,
  "applied_transforms": [],
  "notes": ["Time matched exactly", "Region resolved on curvilinear grid via .where()"]
}
```

### `read_slice(...)` — inline form (size ≤ `max_inline_bytes`)

```json
{
  "form": "inline",
  "values": [[[287.1, 287.4, ...], ...]],
  "coords": {"time": ["2024-09-01T12:00"], "lat": [...], "lon": [...]},
  "dims": ["time", "lat", "lon"],
  "shape": [1, 50, 60],
  "units": "K",
  "stats": {"min": 285.1, "max": 295.2, "mean": 290.1, "fraction_nan": 0.0}
}
```

### `read_slice(...)` — file form (size > `max_inline_bytes`)

```json
{
  "form": "file",
  "path": ".ncplot/slices/<session>/<hash>.nc",
  "format": "netcdf",
  "size_bytes": 4640000,
  "dims": ["time", "lat", "lon"],
  "shape": [1, 290, 200],
  "coords_summary": {
    "time": {"n": 1, "range": ["2024-09-01T12:00"]},
    "lat":  {"n": 290, "range": [25.1, 50.4]},
    "lon":  {"n": 200, "range": [-130.2, -90.1]}
  },
  "units": "K",
  "stats": {"min": 270.2, "max": 312.1, "mean": 291.0, "fraction_nan": 0.13}
}
```

Default `max_inline_bytes = 100_000`. Skills can bump for analysis tasks.

### `compute_stats(...)`

```json
{
  "min": 270.2, "max": 312.1, "mean": 291.0, "std": 7.4,
  "count": 58000, "fraction_nan": 0.13,
  "percentiles": {"p5": 278.4, "p50": 291.0, "p95": 305.1},
  "units": "K",
  "shape_summarized": [1, 290, 200]
}
```

Always inline. Lazy/dask under the hood; never loads the full array.

### `peek(...)`

```json
{
  "value": 287.3,
  "shape": [],
  "coords": {"time": "2024-09-01T12:00", "lat": 42.31, "lon": -71.05},
  "units": "K",
  "distance_to_nearest": {"lat_deg": 0.01, "lon_deg": 0.02, "time": "PT0S"}
}
```

When called with scalar lat/lon, returns the value at the nearest grid cell *and* reports `distance_to_nearest`. Doesn't refuse points outside the file extent unless they're more than one grid cell beyond the boundary (`out_of_bounds`).

### `regrid_to_centers(spec)`

Returns the input `spec` augmented with a `regrid_to_centers` entry in `applied_transforms`. No data read.

### `find_variables(path, hint)`

```json
{
  "matches": [
    {"name": "T2", "score": 0.95, "matched_field": "long_name",
     "matched_value": "Temperature at 2m", "long_name": "Temperature at 2m",
     "units": "K"},
    {"name": "TSK", "score": 0.62, "matched_field": "description",
     "matched_value": "Skin temperature", "long_name": "Surface skin temperature",
     "units": "K"}
  ]
}
```

Top 10 ranked.

### `find_time(path, hint)`

```json
{
  "matches": [
    {"resolved_time": "2024-09-01T12:00:00", "index": 5,
     "match_kind": "exact", "distance": "PT0S"},
    {"resolved_time": "2024-09-01T11:00:00", "index": 4,
     "match_kind": "previous", "distance": "PT1H"}
  ]
}
```

### Encoding rules

- All array values in inline form are JSON-serializable nested lists (no base64, no binary)
- NaN serialized as the string `"NaN"` — skills coerce back
- Datetimes serialized as ISO-8601 strings
- Timedeltas serialized as ISO-8601 duration strings (`"PT1H"`, `"P15D"`)

---

## 11. Multi-format extension seam

Cycle 1 ships a single MCP for NetCDF, but the architecture is designed for adding Zarr / GRIB / HDF5 readers in later cycles **without refactor**.

### Format-agnostic vs format-specific (the seam)

**Format-agnostic** — works for any `xarray.Dataset` regardless of underlying format:

- Response envelope shape + error/warning code taxonomy
- Selector grammar parsing
- Inspection cache (mtime-aware hashing)
- SSH transport + credential-prompt flow (paramiko opens an SFTP file-like; xarray reads through it; doesn't care what's on the other side)
- Path classification (local / glob / URL / SSH)
- Generic tool implementations: `find_variables`, `find_time`, `peek`, `compute_stats`, `read_slice` inline-vs-file branching
- CF-convention detection
- `regrid_to_centers` (works on any `xarray.Dataset` with staggered dim names)

**Format-specific** — differs per format:

- File opening (NetCDF: `engine='netcdf4'` / `engine='h5netcdf'`; Zarr: `engine='zarr'` + store; GRIB: `engine='cfgrib'`)
- Multi-file expansion (NetCDF/HDF5: glob over files; Zarr: a single store *is* the dataset; GRIB: one file usually contains many messages)
- Format-specific convention detection (NetCDF carries WRF/ROMS via attrs; GRIB has its own param tables; Zarr usually mirrors CF)
- Format-specific schemes (NetCDF: `file/http/https/ssh`; Zarr: `file/s3/gs/abfs`; GRIB: usually local-only)

### Adapter protocol (designed now, lifted to `_core/` later)

```python
class FormatAdapter(Protocol):
    name: str                              # e.g., "netcdf"
    supported_schemes: set[str]            # e.g., {"file", "http", "https", "ssh"}

    def claims(self, path: str) -> bool:
        """Does this path look like my format? (suffix, store layout, content peek)"""

    def expand(self, path: str) -> list[str]:
        """Expand a path/glob into a concrete list of file/store identifiers."""

    def open(self, paths: list[str], file_objects: list | None = None) -> xarray.Dataset:
        """Open as an xarray.Dataset. file_objects supplied for SSH/file-like paths."""

    def detect_conventions(self, ds: xarray.Dataset, attrs: dict) -> ConventionResult:
        """Format-specific convention detection on top of core CF detection."""
```

The cycle-1 reader implements one adapter (`NetCDFAdapter`). Generic tools take the adapter as a dependency. Five methods. Don't speculatively expand.

### Future layout (not cycle 1)

```
src/mcp/
├── _core/                    # lifted from netcdf-reader
│   ├── envelope.py, cache.py, selectors.py
│   ├── paths/{classify.py, ssh.py}
│   ├── conventions/cf.py
│   └── tools/{...}
├── netcdf-reader/            # NetCDFAdapter + WRF/ROMS conventions + multi_file glob
├── zarr-reader/              # ZarrAdapter (uses _core; zarr engine + store schemes)
├── grib-reader/              # GRIBAdapter (uses _core; cfgrib + param tables)
└── hdf5-reader/              # HDF5Adapter (uses _core; reuses most NetCDF logic)
```

### Cycle-1 discipline this implies

- Generic tools in `tools/` **must not** call `xarray.open_dataset` directly. They go through `adapter.open(...)` so we don't bake NetCDF assumptions
- `paths/classify.py` returns a scheme; the adapter decides whether that scheme is supported via `adapter.supported_schemes`
- `conventions/cf.py` only handles CF — it does not import WRF or ROMS code
- `paths/ssh.py` returns SFTP file-like objects, never NetCDF-aware data

### Honest tradeoff

Building the seam now without a second consumer means the abstraction is unverified. The `FormatAdapter` protocol might be subtly wrong for Zarr (where `path` and `store` are different concepts) or GRIB (where one file contains many messages). We'll only know when we write the second adapter. **Mitigation:** keep the protocol minimal (5 methods); revise when we hit the first place it doesn't fit.

---

## 12. Testing strategy

### Tier 1 — Unit tests against synthetic fixtures

Each test creates a small NetCDF in `tmp_path` using `xarray.Dataset(...).to_netcdf(...)`. Fixtures cover:

- A 4D CF dataset (`time, plev, lat, lon`) — clean-path resolve_spec / read_slice / compute_stats
- A WRF-mimic file (staggered dims, `Times` byte-string array, `TITLE` global attr) — convention detection + destaggering
- A ROMS-mimic file (`s_rho`, 2D `lat_rho`/`lon_rho`) — curvilinear path
- A CMIP-mimic file (`Conventions: "CF-1.7"`, `mip_era`) — convention detection + clean-path
- A multi-file split (3 files concat-on-time) — `open_mfdataset` path
- A file with deliberately ambiguous convention signals — candidates path
- A file with non-monotonic time / constant field / high-NaN field — warning emission

CI runs Tier 1 on every push. ~seconds.

### Tier 2 — Integration tests against pinned real samples

Small `tests/data/` directory (gitignored, downloaded once via a script):

- One real WRF output snippet (one timestep, single domain, < 50 MB)
- One real ERA5 monthly file (single variable, short time range)
- One ROMS output snippet

Run only with `NCPLOT_INTEGRATION=1`. Marks: `pytest -m integration`. CI runs nightly.

### Tier 3a — SSH unit tests (mocked)

`paramiko.SFTPClient` mocked with `unittest.mock`. Verify:

- Credential-prompt flow returns the correct `ssh_auth_needed` envelope
- Connection-pool reuse
- Multi-step auth handling
- Credential-zeroing on shutdown

### Tier 3b — Real-SSH integration (opt-in)

Configurable via env vars: `NCPLOT_REAL_SSH_HOST`, `NCPLOT_REAL_SSH_USER`, optional `NCPLOT_REAL_SSH_PORT` / `NCPLOT_REAL_SSH_KEY_PATH` / `NCPLOT_REAL_SSH_PASSWORD` (the last via a `.env.test` file that's gitignored), and `NCPLOT_REAL_SSH_FIXTURE_PATH`.

Tests verify:

1. Successful connect via the silent auth chain when keys are configured
2. `inspect()` and `read_slice()` round-trip against the real remote
3. Credential-prompt flow returns a well-formed `ssh_auth_needed` when explicit auth is forced
4. Connection pool reuse across multiple calls
5. `slow_remote_read` warning emission for large slices

Marked `pytest -m real_ssh`. Skipped in CI by default. Setup guide at `tests/REAL_SSH_SETUP.md`.

**Credential-redaction property:** passwords from env vars must not appear in any pytest output, log, or temp file. A grep-the-output assertion enforces this in every Tier 3 test.

### Properties pinned by tests

- Cache invalidation triggers when source mtime changes
- Multi-file cache key changes when a new file is added to the glob
- `peek` enforces the 10 KB hard cap
- `read_slice` switches between inline and file form at the configured threshold
- Selectors with `nearest` matches return `time_match: "nearest"` (don't silently snap)
- Ambiguity envelope shape is identical across all subtypes
- Sensitive-string fields (passwords, passphrases, OTP responses) are absent from any logging, error messages, or cached output

### Non-goals for cycle-1 testing

- No load/perf benchmarks
- No fuzzing of NetCDF readers (xarray + netCDF4 already heavily tested upstream)
- No mutation testing
- No dask cluster tests; we use the default threaded scheduler

### Lint/typecheck

Existing `make lint` covers `ruff` + `mypy`. The reader's public API gets full type hints; internal helpers are best-effort.

---

## 13. Module layout

```
src/mcp/netcdf-reader/
├── pyproject.toml
├── README.md                        # tool list, envelope shape, install + setup
├── server.py                        # MCP dispatch; thin (~50 lines)
│
├── adapter.py                       # NetCDFAdapter (format-specific)
│
├── envelope.py                      # ⤴ format-agnostic — lift to _core/ in future
├── cache.py                         # ⤴
├── selectors.py                     # ⤴
│
├── paths/
│   ├── classify.py                  # ⤴ scheme detection
│   ├── ssh.py                       # ⤴ paramiko + connection pool + creds
│   └── multi_file.py                # NetCDF-specific glob → open_mfdataset
│
├── conventions/
│   ├── cf.py                        # ⤴ generic CF detection
│   ├── wrf.py                       # NetCDF-specific
│   └── roms.py                      # NetCDF-specific
│
└── tools/
    ├── inspect.py                   # ⤴ generic — takes an adapter
    ├── resolve_spec.py              # ⤴
    ├── read_slice.py                # ⤴
    ├── compute_stats.py             # ⤴
    ├── peek.py                      # ⤴
    ├── find.py                      # ⤴
    └── transforms.py                # ⤴ regrid_to_centers (annotation only)

tests/mcp/netcdf-reader/
├── conftest.py                      # synthetic fixture builders
├── unit/
│   ├── test_envelope.py
│   ├── test_selectors.py
│   ├── test_cache.py
│   ├── test_classify.py
│   ├── test_inspect.py
│   ├── test_resolve_spec.py
│   ├── test_read_slice.py
│   ├── test_compute_stats.py
│   ├── test_peek.py
│   ├── test_find.py
│   ├── test_conventions_cf.py
│   ├── test_conventions_wrf.py
│   ├── test_conventions_roms.py
│   └── test_ssh_mocked.py
└── integration/
    ├── test_real_files.py           # NCPLOT_INTEGRATION=1
    └── test_real_ssh.py             # NCPLOT_REAL_SSH=1
```

The `⤴` marker tags every file destined for `_core/` extraction once a second format adapter exists. Convention enforced by:

1. A one-line header comment in each file: `# ⤴ format-agnostic — eligible for _core/ lift`
2. A smoke test in `tests/mcp/netcdf-reader/conftest.py` (or `unit/test_seam.py`) that asserts no `⤴`-marked module imports from non-`⤴` modules. Catches drift automatically.

---

## 14. Open risks and tradeoffs

Honest list of what could bite us, with mitigations.

| Risk | Severity | Mitigation |
|------|---------|-----------|
| `FormatAdapter` protocol unverified until cycle 7+ | Medium | Keep it minimal (5 methods); revise on first mismatch |
| SFTP streaming slow for B-tier files | Medium | `slow_remote_read` warning; future cycle adds sshfs/staging |
| `xarray.open_mfdataset` `combine="by_coords"` fails on real WRF outputs | Medium | Fallback to `combine="nested"`; structured `multi_file_combine_failed` if both fail |
| Inspection cache key on remote URLs has no mtime → stale | Low | Documented; users who care can manually delete cache |
| WRF/ROMS heavyweight transforms missing on day one | Medium | `convention_transform_unavailable` error with cycle-5 install hint |
| Sensitive credentials leak into logs | High | Pinned by every Tier 3 test; grep-the-output assertion |
| Inspection on huge files via `xarray.open_dataset(decode_times=True)` is slow | Medium | First-call cost only; cached after; later cycle could add header-only mode |
| `h5netcdf` engine doesn't handle some NetCDF-3-classic files via SSH file-like | Low | Document; user can SFTP-stage manually as workaround |
| Cycle 1 surface (9 tools) is large for a first MCP | Medium | Each tool is small in isolation; share core helpers |

---

## 15. Cross-cutting principles (for the whole reader)

- **Ask when ambiguous, never silently guess.** Convention, variable, time, region, SSH auth — all surface candidates with reasons rather than picking
- **Strict canonical input + helpful resolution tools.** Data tools take canonical forms; `find_variables` / `find_time` provide hint-based resolution that skills (or pure-MCP users) can use
- **Echo every resolved value.** Every selector returns what was actually used (resolved time, applied transforms, lon shift). Skills relay this back to the user
- **Format-agnostic by design.** Generic tools take an adapter dependency, never hardcode NetCDF
- **Read-only.** No `write_slice`, no derived-variable persistence

---

## Implementation entry point

This design feeds into a `writing-plans` cycle that produces an implementation plan. The plan should:

- Sequence the modules so the format-agnostic core is built first, with the `NetCDFAdapter` slotted in last
- Identify the smallest end-to-end thin slice (probably: `inspect` + `resolve_spec` against a single local CF file → enough to feed the cycle-2 renderer's first prototype)
- Schedule SSH support as its own implementation phase (high complexity, mockable)
- Schedule WRF/ROMS convention detection after the CF-only end-to-end works

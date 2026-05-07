# Cycle 1: `netcdf-reader` MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `netcdf-reader` MCP server per `docs/specs/2026-05-06-cycle-1-netcdf-reader.md`. End state: an MCP server that exposes 8 callable tools for inspecting and reading NetCDF data — supporting local single files, multi-file globs, remote URLs, and SSH-served files — with a structured response envelope, a credential-prompt flow for SSH, and CF/WRF/ROMS convention detection.

**Architecture:** One MCP server organized as `core (envelope, cache, selectors, paths) + adapter (NetCDFAdapter) + conventions (CF/WRF/ROMS) + tools`. Format-agnostic modules are tagged `⤴` and importable without NetCDF assumptions, so future Zarr/GRIB/HDF5 readers can lift them into a shared `_core/` package without refactor. TDD: write failing test → minimal implementation → green → commit. Frequent commits.

**Tech Stack:** Python 3.10+, `xarray`, `netCDF4`, `h5netcdf`, `cftime`, `numpy`, `paramiko`, `mcp`, `pytest`, `ruff`, `mypy`. Optional later: `xwrf`, `xroms`, `s3fs`.

**Before starting:** create a feature branch from master.

```bash
git checkout -b cycle-1-netcdf-reader
```

> **⚠ Naming convention — read this once.** Python packages cannot contain hyphens, so the on-disk Python package directory uses **underscore**: `src/mcp/netcdf_reader/` (not `netcdf-reader`). The MCP server's externally-visible string name is still `netcdf-reader` (hyphen) — that's set in `Server("netcdf-reader")` and in the entry-point script name `ncplot-netcdf-reader`. The existing scaffold's hyphenated stub at `src/mcp/netcdf-reader/` should be renamed to `src/mcp/netcdf_reader/` as part of Task 1 (the existing files are stubs and will be overwritten anyway). Test paths likewise use `tests/mcp/netcdf_reader/` (underscore).
>
> **In every "Files:" list and `git add` command in this plan, treat `netcdf-reader` as a typo for `netcdf_reader`.** The plan was drafted with the spec's hyphenated naming; this single discrepancy is resolved on disk by always using underscore. No other rename is required.

---

## File Structure

### Source files (`src/mcp/netcdf-reader/`)

| File | Responsibility | Format-agnostic? |
|------|----------------|-----------|
| `pyproject.toml` | Package metadata + deps | n/a |
| `README.md` | Tool list, envelope shape, install + setup | n/a |
| `server.py` | Thin MCP dispatch (~50 lines) | n/a |
| `adapter.py` | `NetCDFAdapter` — format-specific opening | NO |
| `envelope.py` | Success/error/ambiguity envelopes, error/warning codes | ⤴ YES |
| `cache.py` | Inspection cache (hash, read, write, invalidate) | ⤴ YES |
| `selectors.py` | Canonical selector parsing/validation | ⤴ YES |
| `paths/classify.py` | Path scheme detection (local/glob/url/ssh) | ⤴ YES |
| `paths/ssh.py` | paramiko + SFTP file-like + connection pool + creds | ⤴ YES |
| `paths/multi_file.py` | NetCDF-specific glob → `open_mfdataset` | NO |
| `conventions/cf.py` | CF detection + variable/coord/time extraction | ⤴ YES |
| `conventions/wrf.py` | WRF detection + Times decoding + destaggering | NO |
| `conventions/roms.py` | ROMS detection + curvilinear coord recognition | NO |
| `tools/inspect.py` | `inspect()` tool | ⤴ YES |
| `tools/resolve_spec.py` | `resolve_spec()` tool | ⤴ YES |
| `tools/read_slice.py` | `read_slice()` tool (inline + file forms) | ⤴ YES |
| `tools/compute_stats.py` | `compute_stats()` tool | ⤴ YES |
| `tools/peek.py` | `peek()` tool | ⤴ YES |
| `tools/find.py` | `find_variables()` + `find_time()` tools | ⤴ YES |
| `tools/transforms.py` | `regrid_to_centers()` spec annotation | ⤴ YES |

### Test files (`tests/mcp/netcdf-reader/`)

| File | Tests |
|------|-------|
| `conftest.py` | Synthetic fixture builders (CF, WRF, ROMS, multi-file, ambiguous) |
| `unit/test_envelope.py` | Envelope helpers, code taxonomies |
| `unit/test_selectors.py` | Time/level/lat/lon parsing |
| `unit/test_cache.py` | Hash, mtime invalidation, multi-file keys |
| `unit/test_classify.py` | Path scheme detection |
| `unit/test_conventions_cf.py` | CF detection, time/coord extraction |
| `unit/test_conventions_wrf.py` | WRF detection, Times decoding, destaggering |
| `unit/test_conventions_roms.py` | ROMS detection, curvilinear coords |
| `unit/test_inspect.py` | `inspect()` tool end-to-end (synthetic) |
| `unit/test_resolve_spec.py` | Selector resolution + nearest matching |
| `unit/test_read_slice.py` | Inline form + file form |
| `unit/test_compute_stats.py` | Stats correctness |
| `unit/test_peek.py` | Single-point + tiny-area + hard cap |
| `unit/test_find.py` | `find_variables` + `find_time` |
| `unit/test_transforms.py` | `regrid_to_centers` spec annotation |
| `unit/test_multi_file.py` | Glob expansion, combine fallback |
| `unit/test_ssh_mocked.py` | Silent auth chain, prompt flow, pool, security |
| `unit/test_seam.py` | Format-agnostic modules don't import format-specific |
| `unit/test_server.py` | MCP dispatch, lifecycle hook |
| `integration/test_real_files.py` | Pinned real samples (`NCPLOT_INTEGRATION=1`) |
| `integration/test_real_ssh.py` | Real SSH endpoint (`NCPLOT_REAL_SSH=1`) |
| `REAL_SSH_SETUP.md` | Setup guide for real-SSH integration tests |

---

## Phase 1: Foundation (cross-cutting types)

End of phase: envelope helpers, selector parsing, and cache module are tested and working — no format-specific code yet.

### Task 1: Set up package skeleton

**Files (recall the naming convention: hyphens in the spec → underscores on disk):**
- Rename: `src/mcp/netcdf-reader/` → `src/mcp/netcdf_reader/` (existing stub directory)
- Create: `src/mcp/netcdf_reader/pyproject.toml` (overwrite renamed stub)
- Create: `src/mcp/netcdf_reader/__init__.py`
- Create: `src/mcp/netcdf_reader/paths/__init__.py`
- Create: `src/mcp/netcdf_reader/conventions/__init__.py`
- Create: `src/mcp/netcdf_reader/tools/__init__.py`
- Create: `tests/mcp/netcdf_reader/__init__.py`
- Create: `tests/mcp/netcdf_reader/unit/__init__.py`
- Create: `tests/mcp/netcdf_reader/integration/__init__.py`

- [ ] **Step 0: Rename the hyphenated stub directory to underscore**

```bash
git mv src/mcp/netcdf-reader src/mcp/netcdf_reader
```

This preserves git history on the existing `pyproject.toml`, `README.md`, and `server.py` stubs (all of which are about to be overwritten anyway).

- [ ] **Step 1: Replace `src/mcp/netcdf_reader/pyproject.toml` with the cycle-1 deps**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "ncplot-netcdf-reader"
version = "0.1.0"
description = "MCP server for inspecting and reading NetCDF data"
requires-python = ">=3.10"
dependencies = [
  "mcp>=1.0",
  "xarray>=2024.1",
  "netcdf4>=1.6",
  "h5netcdf>=1.3",
  "cftime>=1.6",
  "numpy>=1.24",
  "paramiko>=3.4",
]

[project.optional-dependencies]
dev = ["pytest>=7.4", "pytest-mock>=3.12", "ruff>=0.4", "mypy>=1.8"]
remote = ["s3fs>=2024.1"]
wrf = ["xwrf>=0.0.3"]
roms = ["xroms>=0.5"]

[project.scripts]
ncplot-netcdf-reader = "src.mcp.netcdf_reader.server:main"
```

- [ ] **Step 2: Create empty `__init__.py` for each subpackage**

```bash
touch src/mcp/netcdf-reader/__init__.py \
      src/mcp/netcdf-reader/paths/__init__.py \
      src/mcp/netcdf-reader/conventions/__init__.py \
      src/mcp/netcdf-reader/tools/__init__.py \
      tests/mcp/netcdf-reader/__init__.py \
      tests/mcp/netcdf-reader/unit/__init__.py \
      tests/mcp/netcdf-reader/integration/__init__.py
```

- [ ] **Step 3: Verify the package imports**

```bash
pip install -e 'src/mcp/netcdf-reader[dev]'
python -c "import importlib; importlib.import_module('src.mcp.netcdf-reader' if False else 'mcp')"
```

(The hyphen in the directory name means we won't `import src.mcp.netcdf-reader` directly — modules below it get installed via `setuptools.find_packages`. Step 4 confirms.)

- [ ] **Step 4: Commit**

```bash
git add src/mcp/netcdf-reader/pyproject.toml src/mcp/netcdf-reader/__init__.py \
        src/mcp/netcdf-reader/paths/__init__.py \
        src/mcp/netcdf-reader/conventions/__init__.py \
        src/mcp/netcdf-reader/tools/__init__.py \
        tests/mcp/netcdf-reader/
git commit -m "scaffold cycle-1 netcdf-reader package skeleton"
```

---

### Task 2: Envelope dataclasses and constants

**Files:**
- Create: `src/mcp/netcdf-reader/envelope.py`
- Create: `tests/mcp/netcdf-reader/unit/test_envelope.py`

- [ ] **Step 1: Write the failing test for `success()` envelope**

```python
# tests/mcp/netcdf-reader/unit/test_envelope.py
from src.mcp.netcdf_reader.envelope import success

def test_success_envelope_minimal():
    env = success({"foo": "bar"})
    assert env == {
        "ok": True,
        "result": {"foo": "bar"},
        "warnings": [],
        "resolved": {},
    }

def test_success_envelope_with_warnings_and_resolved():
    env = success(
        {"value": 1},
        warnings=[{"code": "slow_remote_read", "message": "took 45s", "context": {}}],
        resolved={"time_value": "2024-09-01T12:00:00"},
    )
    assert env["ok"] is True
    assert len(env["warnings"]) == 1
    assert env["warnings"][0]["code"] == "slow_remote_read"
    assert env["resolved"] == {"time_value": "2024-09-01T12:00:00"}
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_envelope.py -v
```

Expected: `ImportError: cannot import name 'success'` or `ModuleNotFoundError`.

- [ ] **Step 3: Implement `envelope.py`**

```python
# src/mcp/netcdf-reader/envelope.py
"""⤴ format-agnostic — eligible for _core/ lift.

Response-envelope helpers and code taxonomies. Every tool returns one
of three envelope shapes: success, error, or ambiguity (the last is
itself an error envelope with code='ambiguous' and a list of candidates).
"""
from __future__ import annotations

from typing import Any


def success(
    result: dict[str, Any],
    *,
    warnings: list[dict[str, Any]] | None = None,
    resolved: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": True,
        "result": result,
        "warnings": warnings or [],
        "resolved": resolved or {},
    }


def error(
    code: str,
    message: str,
    *,
    context: dict[str, Any] | None = None,
    warnings: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {"code": code, "message": message, "context": context or {}},
        "warnings": warnings or [],
    }


def ambiguous(
    subcode: str,
    message: str,
    *,
    candidates: list[dict[str, Any]],
    prompt: str,
    retry_with_param: str,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "ok": False,
        "error": {
            "code": "ambiguous",
            "subcode": subcode,
            "message": message,
            "candidates": candidates,
            "prompt": prompt,
            "retry_with_param": retry_with_param,
            "context": context or {},
        },
        "warnings": [],
    }


def warn(code: str, message: str, *, context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "context": context or {}}
```

- [ ] **Step 4: Run the test to verify it passes**

```bash
pytest tests/mcp/netcdf-reader/unit/test_envelope.py -v
```

Expected: `2 passed`.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/envelope.py \
        tests/mcp/netcdf-reader/unit/test_envelope.py
git commit -m "envelope: success/error/ambiguous helpers"
```

---

### Task 3: Error and warning code constants

**Files:**
- Modify: `src/mcp/netcdf-reader/envelope.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_envelope.py`

- [ ] **Step 1: Append failing tests for code constants**

```python
# Append to tests/mcp/netcdf-reader/unit/test_envelope.py
from src.mcp.netcdf_reader.envelope import ErrorCode, WarningCode, error, ambiguous

def test_error_code_constants_present():
    assert ErrorCode.FILE_NOT_FOUND == "file_not_found"
    assert ErrorCode.REMOTE_FILE_NOT_FOUND == "remote_file_not_found"
    assert ErrorCode.MULTI_FILE_COMBINE_FAILED == "multi_file_combine_failed"
    assert ErrorCode.SSH_AUTH_FAILED == "ssh_auth_failed"
    assert ErrorCode.UNKNOWN_VARIABLE == "unknown_variable"
    assert ErrorCode.OUT_OF_BOUNDS == "out_of_bounds"
    assert ErrorCode.EMPTY_SLICE == "empty_slice"
    assert ErrorCode.SIZE_LIMIT_EXCEEDED == "size_limit_exceeded"
    assert ErrorCode.CONVENTION_TRANSFORM_UNAVAILABLE == "convention_transform_unavailable"
    assert ErrorCode.NOT_4D == "not_4d"
    assert ErrorCode.AMBIGUOUS == "ambiguous"

def test_warning_code_constants_present():
    assert WarningCode.SLOW_REMOTE_READ == "slow_remote_read"
    assert WarningCode.HIGH_NAN_FRACTION == "high_nan_fraction"
    assert WarningCode.CONSTANT_FIELD == "constant_field"
    assert WarningCode.NON_MONOTONIC_COORD == "non_monotonic_coord"
    assert WarningCode.NON_STANDARD_CALENDAR == "non_standard_calendar"
    assert WarningCode.PERCENTILE_CLIP_SUGGESTED == "percentile_clip_suggested"

def test_error_uses_code_constants():
    env = error(ErrorCode.FILE_NOT_FOUND, "nope")
    assert env["error"]["code"] == "file_not_found"
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_envelope.py -v -k "code_constants or uses_code"
```

Expected: `ImportError: cannot import name 'ErrorCode'`.

- [ ] **Step 3: Add code constants to `envelope.py`**

```python
# Append to src/mcp/netcdf-reader/envelope.py

class ErrorCode:
    FILE_NOT_FOUND = "file_not_found"
    REMOTE_FILE_NOT_FOUND = "remote_file_not_found"
    REMOTE_PERMISSION_DENIED = "remote_permission_denied"
    MULTI_FILE_COMBINE_FAILED = "multi_file_combine_failed"
    UNSUPPORTED_PATH_SCHEME = "unsupported_path_scheme"
    SSH_AUTH_FAILED = "ssh_auth_failed"
    SSH_TIMEOUT = "ssh_timeout"
    UNKNOWN_VARIABLE = "unknown_variable"
    OUT_OF_BOUNDS = "out_of_bounds"
    EMPTY_SLICE = "empty_slice"
    SIZE_LIMIT_EXCEEDED = "size_limit_exceeded"
    CONVENTION_TRANSFORM_UNAVAILABLE = "convention_transform_unavailable"
    NOT_4D = "not_4d"
    INTERNAL_ERROR = "internal_error"
    AMBIGUOUS = "ambiguous"


class AmbiguitySubcode:
    CONVENTION = "convention"
    VARIABLE = "variable"
    SSH_AUTH_NEEDED = "ssh_auth_needed"
    TIME_MATCH = "time_match"
    REGION = "region"
    MULTI_FILE_COMBINE = "multi_file_combine"


class WarningCode:
    SLOW_REMOTE_READ = "slow_remote_read"
    HIGH_NAN_FRACTION = "high_nan_fraction"
    CONSTANT_FIELD = "constant_field"
    NON_MONOTONIC_COORD = "non_monotonic_coord"
    NON_STANDARD_CALENDAR = "non_standard_calendar"
    PERCENTILE_CLIP_SUGGESTED = "percentile_clip_suggested"
```

- [ ] **Step 4: Verify all tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_envelope.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/envelope.py tests/mcp/netcdf-reader/unit/test_envelope.py
git commit -m "envelope: error/warning/ambiguity-subcode constants"
```

---

### Task 4: Selector dataclasses

**Files:**
- Create: `src/mcp/netcdf-reader/selectors.py`
- Create: `tests/mcp/netcdf-reader/unit/test_selectors.py`

- [ ] **Step 1: Write failing tests for selector parsing**

```python
# tests/mcp/netcdf-reader/unit/test_selectors.py
import pytest
from src.mcp.netcdf_reader.selectors import (
    parse_time, parse_level, parse_latlon,
    TimeSelector, LevelSelector, LatLonSelector,
    SelectorError,
)


def test_parse_time_iso_string():
    sel = parse_time("2024-09-15")
    assert isinstance(sel, TimeSelector)
    assert sel.kind == "iso"
    assert sel.value == "2024-09-15"


def test_parse_time_range():
    sel = parse_time(["2024-01", "2024-12"])
    assert sel.kind == "range"
    assert sel.value == ["2024-01", "2024-12"]


def test_parse_time_index():
    sel = parse_time({"index": 5})
    assert sel.kind == "index"
    assert sel.value == 5


def test_parse_time_index_list():
    sel = parse_time({"index": [0, 6, 12]})
    assert sel.kind == "index_list"
    assert sel.value == [0, 6, 12]


def test_parse_time_sentinel():
    assert parse_time("first").kind == "sentinel"
    assert parse_time("first").value == "first"
    assert parse_time("last").value == "last"


def test_parse_time_invalid():
    with pytest.raises(SelectorError):
        parse_time(42.5)


def test_parse_level_numeric():
    sel = parse_level(500)
    assert sel.kind == "numeric"
    assert sel.value == 500


def test_parse_level_list():
    sel = parse_level([500, 850, 1000])
    assert sel.kind == "list"
    assert sel.value == [500, 850, 1000]


def test_parse_level_sentinel():
    assert parse_level("surface").value == "surface"
    assert parse_level("top").value == "top"


def test_parse_latlon_bbox():
    sel = parse_latlon([20, 70])
    assert sel.kind == "bbox"
    assert sel.value == [20, 70]


def test_parse_latlon_point():
    sel = parse_latlon(42.3)
    assert sel.kind == "point"
    assert sel.value == 42.3


def test_parse_latlon_index():
    sel = parse_latlon({"index": [0, 100]})
    assert sel.kind == "index"
    assert sel.value == [0, 100]
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_selectors.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `selectors.py`**

```python
# src/mcp/netcdf-reader/selectors.py
"""⤴ format-agnostic — eligible for _core/ lift.

Canonical selector parsing. Skills do natural-language translation;
this module does deterministic resolution. See spec §5.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


class SelectorError(ValueError):
    pass


@dataclass
class TimeSelector:
    kind: str  # "iso" | "range" | "index" | "index_list" | "sentinel"
    value: Any


@dataclass
class LevelSelector:
    kind: str  # "numeric" | "list" | "index" | "index_list" | "sentinel"
    value: Any


@dataclass
class LatLonSelector:
    kind: str  # "bbox" | "point" | "index"
    value: Any


def parse_time(raw: Any) -> TimeSelector:
    if isinstance(raw, str):
        if raw in ("first", "last"):
            return TimeSelector("sentinel", raw)
        return TimeSelector("iso", raw)
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(x, str) for x in raw):
        return TimeSelector("range", raw)
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, int):
            return TimeSelector("index", idx)
        if isinstance(idx, list) and all(isinstance(x, int) for x in idx):
            return TimeSelector("index_list", idx)
    raise SelectorError(f"unrecognized time selector: {raw!r}")


def parse_level(raw: Any) -> LevelSelector:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return LevelSelector("numeric", raw)
    if isinstance(raw, list) and all(isinstance(x, (int, float)) for x in raw):
        return LevelSelector("list", list(raw))
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, int):
            return LevelSelector("index", idx)
        if isinstance(idx, list) and all(isinstance(x, int) for x in idx):
            return LevelSelector("index_list", idx)
    if isinstance(raw, str) and raw in ("surface", "top"):
        return LevelSelector("sentinel", raw)
    raise SelectorError(f"unrecognized level selector: {raw!r}")


def parse_latlon(raw: Any) -> LatLonSelector:
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return LatLonSelector("point", float(raw))
    if isinstance(raw, list) and len(raw) == 2 and all(isinstance(x, (int, float)) for x in raw):
        return LatLonSelector("bbox", [float(raw[0]), float(raw[1])])
    if isinstance(raw, dict) and "index" in raw:
        idx = raw["index"]
        if isinstance(idx, list) and len(idx) == 2 and all(isinstance(x, int) for x in idx):
            return LatLonSelector("index", idx)
    raise SelectorError(f"unrecognized lat/lon selector: {raw!r}")
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_selectors.py -v
```

Expected: all 14 tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/selectors.py tests/mcp/netcdf-reader/unit/test_selectors.py
git commit -m "selectors: time/level/lat-lon canonical parsing"
```

---

### Task 5: Inspection cache hash and read/write

**Files:**
- Create: `src/mcp/netcdf-reader/cache.py`
- Create: `tests/mcp/netcdf-reader/unit/test_cache.py`

- [ ] **Step 1: Write failing tests for cache key + read/write**

```python
# tests/mcp/netcdf-reader/unit/test_cache.py
import json
from pathlib import Path
import pytest
from src.mcp.netcdf_reader.cache import (
    inspection_key, read_inspection, write_inspection, InspectionCache,
)


def test_inspection_key_local_single(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"x" * 100)
    k1 = inspection_key([str(f)])
    k2 = inspection_key([str(f)])
    assert k1 == k2
    assert isinstance(k1, str)
    assert len(k1) >= 16

def test_inspection_key_changes_with_mtime(tmp_path):
    f = tmp_path / "data.nc"
    f.write_bytes(b"x" * 100)
    k1 = inspection_key([str(f)])
    # bump mtime
    import os, time
    time.sleep(0.01)
    os.utime(f, None)
    k2 = inspection_key([str(f)])
    # Same content but different mtime → different key
    assert k1 != k2

def test_inspection_key_multifile_includes_all(tmp_path):
    f1 = tmp_path / "a.nc"; f1.write_bytes(b"a")
    f2 = tmp_path / "b.nc"; f2.write_bytes(b"b")
    k_pair = inspection_key([str(f1), str(f2)])
    k_single = inspection_key([str(f1)])
    assert k_pair != k_single

def test_inspection_key_remote_url():
    k = inspection_key(["https://example.org/data.nc"], remote=True)
    assert isinstance(k, str)

def test_write_then_read_inspection(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    payload = {"path": str(tmp_path / "x.nc"), "variables": []}
    key = "abc123"
    write_inspection(key, payload)
    out = read_inspection(key)
    assert out == payload

def test_read_inspection_missing_returns_none(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_inspection("nope") is None
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_cache.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `cache.py`**

```python
# src/mcp/netcdf-reader/cache.py
"""⤴ format-agnostic — eligible for _core/ lift.

Inspection cache. Hash key includes path + mtime + size for local files
(the mtime is the invalidation signal); URL-only for remote (with
documented stale-data caveat). Cache lives in the per-project
.ncplot/inspections/ directory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _cache_dir() -> Path:
    return Path.cwd() / ".ncplot" / "inspections"


def inspection_key(paths: list[str], *, remote: bool = False) -> str:
    h = hashlib.sha256()
    if remote:
        for p in sorted(paths):
            h.update(b"REMOTE\x00")
            h.update(p.encode("utf-8"))
            h.update(b"\x00")
    else:
        for p in sorted(paths):
            try:
                stat = Path(p).resolve().stat()
                h.update(p.encode("utf-8"))
                h.update(b"\x00")
                h.update(str(stat.st_mtime_ns).encode("ascii"))
                h.update(b"\x00")
                h.update(str(stat.st_size).encode("ascii"))
                h.update(b"\x00")
            except FileNotFoundError:
                h.update(p.encode("utf-8"))
                h.update(b"\x00MISSING\x00")
    return h.hexdigest()[:32]


def read_inspection(key: str) -> dict[str, Any] | None:
    fp = _cache_dir() / f"{key}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text())
    except json.JSONDecodeError:
        return None


def write_inspection(key: str, payload: dict[str, Any]) -> None:
    d = _cache_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{key}.json").write_text(json.dumps(payload, indent=2))


class InspectionCache:
    """Thin convenience wrapper. Some tests want a class-style interface."""
    def __init__(self) -> None:
        self.dir = _cache_dir()

    def key(self, paths: list[str], *, remote: bool = False) -> str:
        return inspection_key(paths, remote=remote)

    def get(self, key: str) -> dict[str, Any] | None:
        return read_inspection(key)

    def put(self, key: str, payload: dict[str, Any]) -> None:
        write_inspection(key, payload)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_cache.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/cache.py tests/mcp/netcdf-reader/unit/test_cache.py
git commit -m "cache: inspection-cache hash key + read/write helpers"
```

---

### Task 6: Path scheme classification

**Files:**
- Create: `src/mcp/netcdf-reader/paths/classify.py`
- Create: `tests/mcp/netcdf-reader/unit/test_classify.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_classify.py
import pytest
from src.mcp.netcdf_reader.paths.classify import classify, PathKind, ClassifyError


def test_classify_local_single(tmp_path):
    f = tmp_path / "data.nc"; f.write_bytes(b"")
    k = classify(str(f))
    assert k.kind == PathKind.LOCAL_SINGLE
    assert k.scheme == "file"
    assert k.paths == [str(f.resolve())]

def test_classify_file_url(tmp_path):
    f = tmp_path / "data.nc"; f.write_bytes(b"")
    k = classify(f"file://{f}")
    assert k.kind == PathKind.LOCAL_SINGLE

def test_classify_local_glob(tmp_path):
    (tmp_path / "a.nc").write_bytes(b"")
    (tmp_path / "b.nc").write_bytes(b"")
    k = classify(str(tmp_path / "*.nc"))
    assert k.kind == PathKind.LOCAL_MULTI
    assert sorted(k.paths) == [
        str((tmp_path / "a.nc").resolve()),
        str((tmp_path / "b.nc").resolve()),
    ]

def test_classify_local_directory(tmp_path):
    (tmp_path / "a.nc").write_bytes(b"")
    (tmp_path / "b.nc").write_bytes(b"")
    k = classify(str(tmp_path))
    assert k.kind == PathKind.LOCAL_MULTI
    assert len(k.paths) == 2

def test_classify_http_url():
    k = classify("https://example.org/data.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "https"

def test_classify_s3_url():
    k = classify("s3://bucket/key.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "s3"

def test_classify_ssh_url():
    k = classify("ssh://user@host:22/path/to/file.nc")
    assert k.kind == PathKind.SSH_REMOTE
    assert k.scheme == "ssh"
    assert k.user == "user"
    assert k.host == "host"
    assert k.port == 22
    assert k.remote_path == "/path/to/file.nc"

def test_classify_ssh_url_no_user_no_port():
    k = classify("ssh://host/path/file.nc")
    assert k.kind == PathKind.SSH_REMOTE
    assert k.user is None
    assert k.port is None

def test_classify_rejects_ftp():
    with pytest.raises(ClassifyError):
        classify("ftp://example.org/x.nc")

def test_classify_rejects_missing_local(tmp_path):
    with pytest.raises(ClassifyError):
        classify(str(tmp_path / "does-not-exist.nc"))
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_classify.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `paths/classify.py`**

```python
# src/mcp/netcdf-reader/paths/classify.py
"""⤴ format-agnostic — eligible for _core/ lift.

Path scheme detection. Returns a structured ClassifiedPath that the
adapter uses to decide how to open. Format adapters declare which
schemes they support via FormatAdapter.supported_schemes.
"""
from __future__ import annotations

import glob as _glob
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse


class PathKind:
    LOCAL_SINGLE = "local_single"
    LOCAL_MULTI = "local_multi"
    REMOTE_URL = "remote_url"
    SSH_REMOTE = "ssh_remote"


class ClassifyError(ValueError):
    pass


@dataclass
class ClassifiedPath:
    kind: str
    scheme: str
    paths: list[str] = field(default_factory=list)
    user: str | None = None
    host: str | None = None
    port: int | None = None
    remote_path: str | None = None
    raw: str = ""


_SSH_RE = re.compile(
    r"^ssh://(?:(?P<user>[^@]+)@)?(?P<host>[^:/]+)(?::(?P<port>\d+))?(?P<path>/.*)$"
)


def _has_glob(s: str) -> bool:
    return any(c in s for c in ["*", "?", "["])


def classify(raw: str) -> ClassifiedPath:
    if raw.startswith("ssh://"):
        m = _SSH_RE.match(raw)
        if not m:
            raise ClassifyError(f"malformed ssh URL: {raw!r}")
        port = int(m.group("port")) if m.group("port") else None
        return ClassifiedPath(
            kind=PathKind.SSH_REMOTE,
            scheme="ssh",
            user=m.group("user"),
            host=m.group("host"),
            port=port,
            remote_path=m.group("path"),
            raw=raw,
        )

    parsed = urlparse(raw)
    scheme = parsed.scheme.lower()

    if scheme in ("http", "https", "s3", "gs", "abfs"):
        return ClassifiedPath(kind=PathKind.REMOTE_URL, scheme=scheme,
                              paths=[raw], raw=raw)

    if scheme and scheme != "file":
        raise ClassifyError(f"unsupported scheme: {scheme!r} in {raw!r}")

    # Local
    plain = parsed.path if scheme == "file" else raw
    if _has_glob(plain):
        matches = sorted(_glob.glob(plain))
        if not matches:
            raise ClassifyError(f"no files matched glob: {plain!r}")
        return ClassifiedPath(
            kind=PathKind.LOCAL_MULTI, scheme="file",
            paths=[str(Path(m).resolve()) for m in matches], raw=raw,
        )

    p = Path(plain)
    if not p.exists():
        raise ClassifyError(f"path not found: {plain!r}")

    if p.is_dir():
        files = sorted(p.glob("*.nc"))
        if not files:
            raise ClassifyError(f"directory has no .nc files: {plain!r}")
        return ClassifiedPath(
            kind=PathKind.LOCAL_MULTI, scheme="file",
            paths=[str(f.resolve()) for f in files], raw=raw,
        )

    return ClassifiedPath(
        kind=PathKind.LOCAL_SINGLE, scheme="file",
        paths=[str(p.resolve())], raw=raw,
    )
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_classify.py -v
```

Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/classify.py tests/mcp/netcdf-reader/unit/test_classify.py
git commit -m "paths/classify: scheme detection (local/glob/url/ssh)"
```

---

### Task 7: Phase-1 lint and typecheck gate

**Files:**
- Modify: existing if needed; otherwise no-op

- [ ] **Step 1: Run ruff**

```bash
ruff check src/mcp/netcdf-reader/ tests/mcp/netcdf-reader/
```

Fix any reported issues with minimal targeted edits.

- [ ] **Step 2: Run mypy on the package**

```bash
mypy src/mcp/netcdf-reader/
```

Fix any type errors. Add `from __future__ import annotations` if a file is missing it. The selector dataclass field types use `Any` intentionally — that's OK.

- [ ] **Step 3: Run all phase-1 tests once**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: all tests pass (envelope + selectors + cache + classify, ~32 tests total).

- [ ] **Step 4: Commit any fixes**

```bash
git add -A
git diff --cached --quiet || git commit -m "phase-1 lint/typecheck pass"
```

---

## Phase 2: NetCDFAdapter + CF conventions

End of phase: an adapter can open a CF-compliant local single file as `xarray.Dataset`, and CF conventions can extract structured metadata (variables, coords, time, spatial, vertical).

### Task 8: Synthetic-fixture builder for tests

**Files:**
- Create: `tests/mcp/netcdf-reader/conftest.py`

- [ ] **Step 1: Write the conftest with a CF fixture builder**

```python
# tests/mcp/netcdf-reader/conftest.py
"""Synthetic NetCDF fixture builders. Tests should use these instead
of shipping real binary samples whenever possible."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import xarray as xr
import pytest


@pytest.fixture
def cf_4d_file(tmp_path: Path) -> Path:
    """4D CF dataset: time, plev, lat, lon."""
    times = np.array(
        ["2024-09-01T00", "2024-09-01T06", "2024-09-01T12"], dtype="datetime64[h]"
    )
    plev = np.array([1000.0, 850.0, 500.0, 250.0])
    lat = np.linspace(-90, 90, 19)
    lon = np.linspace(-180, 175, 72)
    rng = np.random.default_rng(0)
    data = rng.normal(280, 10, size=(3, 4, 19, 72)).astype("float32")
    ds = xr.Dataset(
        {
            "ta": xr.DataArray(
                data, dims=("time", "plev", "lat", "lon"),
                coords={"time": times, "plev": plev, "lat": lat, "lon": lon},
                attrs={"long_name": "Air Temperature", "units": "K",
                       "standard_name": "air_temperature"},
            ),
        },
        attrs={"Conventions": "CF-1.7", "title": "Synthetic CF 4D fixture"},
    )
    ds["plev"].attrs.update({"units": "hPa", "positive": "down",
                             "standard_name": "air_pressure"})
    ds["lat"].attrs.update({"units": "degrees_north", "standard_name": "latitude"})
    ds["lon"].attrs.update({"units": "degrees_east", "standard_name": "longitude"})
    p = tmp_path / "cf_4d.nc"
    ds.to_netcdf(p)
    return p


@pytest.fixture
def cf_3d_file(tmp_path: Path) -> Path:
    """3D CF dataset: time, lat, lon. No level dim."""
    times = np.array(["2024-09-01", "2024-09-02", "2024-09-03"], dtype="datetime64[D]")
    lat = np.linspace(-90, 90, 19)
    lon = np.linspace(0, 357.5, 144)  # 0..360 convention
    rng = np.random.default_rng(1)
    data = rng.normal(290, 5, size=(3, 19, 144)).astype("float32")
    ds = xr.Dataset(
        {
            "tos": xr.DataArray(
                data, dims=("time", "lat", "lon"),
                coords={"time": times, "lat": lat, "lon": lon},
                attrs={"long_name": "Sea Surface Temperature", "units": "K",
                       "standard_name": "sea_surface_temperature"},
            ),
        },
        attrs={"Conventions": "CF-1.7"},
    )
    ds["lat"].attrs.update({"units": "degrees_north"})
    ds["lon"].attrs.update({"units": "degrees_east"})
    p = tmp_path / "cf_3d.nc"
    ds.to_netcdf(p)
    return p
```

- [ ] **Step 2: Smoke-test the fixture builds without errors**

```python
# Append to tests/mcp/netcdf-reader/conftest.py — actually create
# tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
```

```python
# tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
import xarray as xr

def test_cf_4d_fixture_opens(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    assert "ta" in ds.data_vars
    assert ds["ta"].shape == (3, 4, 19, 72)
    ds.close()

def test_cf_3d_fixture_opens(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert "tos" in ds.data_vars
    assert float(ds["lon"].max()) > 180  # 0..360 convention
    ds.close()
```

- [ ] **Step 3: Run smoke tests**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conftest_smoke.py -v
```

Expected: 2 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/netcdf-reader/conftest.py \
        tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
git commit -m "tests: synthetic CF 3D + 4D fixtures"
```

---

### Task 9: NetCDFAdapter — Protocol + skeleton

**Files:**
- Create: `src/mcp/netcdf-reader/adapter.py`
- Create: `tests/mcp/netcdf-reader/unit/test_adapter.py`

- [ ] **Step 1: Write the failing test for the adapter contract**

```python
# tests/mcp/netcdf-reader/unit/test_adapter.py
import xarray as xr
from src.mcp.netcdf_reader.adapter import NetCDFAdapter, FormatAdapter


def test_adapter_implements_protocol():
    a = NetCDFAdapter()
    assert isinstance(a, FormatAdapter)
    assert a.name == "netcdf"
    assert "file" in a.supported_schemes
    assert "ssh" in a.supported_schemes
    assert "http" in a.supported_schemes
    assert "https" in a.supported_schemes


def test_adapter_claims_nc_files(tmp_path):
    a = NetCDFAdapter()
    nc = tmp_path / "x.nc"; nc.write_bytes(b"")
    assert a.claims(str(nc)) is True
    assert a.claims("https://example.org/x.nc") is True
    assert a.claims("ssh://h/x.nc") is True
    assert a.claims(str(tmp_path / "x.zarr")) is False
    assert a.claims(str(tmp_path / "x.grib2")) is False


def test_adapter_open_local_single(cf_3d_file):
    a = NetCDFAdapter()
    ds = a.open([str(cf_3d_file)])
    assert isinstance(ds, xr.Dataset)
    assert "tos" in ds.data_vars
    ds.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_adapter.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `adapter.py`**

```python
# src/mcp/netcdf-reader/adapter.py
"""Format-specific: NetCDFAdapter implements the FormatAdapter protocol
that lives at the seam between cycle 1's reader and a future _core/
package. See spec §11."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import xarray as xr


@runtime_checkable
class FormatAdapter(Protocol):
    name: str
    supported_schemes: set[str]

    def claims(self, path: str) -> bool: ...
    def expand(self, path: str) -> list[str]: ...
    def open(self, paths: list[str], file_objects: list[Any] | None = None) -> xr.Dataset: ...
    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]: ...


class NetCDFAdapter:
    name = "netcdf"
    supported_schemes = {"file", "http", "https", "s3", "ssh"}

    _NC_SUFFIXES = (".nc", ".nc4", ".cdf")

    def claims(self, path: str) -> bool:
        # Heuristic: any path ending in .nc / .nc4 / .cdf, or any non-store scheme path
        # whose path component ends in those suffixes.
        lowered = path.lower()
        for s in self._NC_SUFFIXES:
            if lowered.endswith(s):
                return True
            # also handle "...?query" or fragment after suffix
            if s + "?" in lowered or s + "#" in lowered:
                return True
        return False

    def expand(self, path: str) -> list[str]:
        # Format-agnostic glob expansion handled in paths.classify.
        # NetCDF specifics live in paths.multi_file (Task 30+).
        return [path]

    def open(self, paths: list[str], file_objects: list[Any] | None = None) -> xr.Dataset:
        if file_objects:
            # One file_object per path; used by SSH path (later task).
            if len(file_objects) != 1:
                raise NotImplementedError("multi-file SSH not yet wired")
            return xr.open_dataset(file_objects[0], engine="h5netcdf",
                                   decode_times=True, chunks="auto")
        if len(paths) == 1:
            return xr.open_dataset(paths[0], decode_times=True, chunks="auto")
        # Multi-file path delegates to paths.multi_file (Task 31)
        from src.mcp.netcdf_reader.paths.multi_file import open_multi_file
        return open_multi_file(paths)

    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
        # CF detection lives in conventions/cf.py; WRF/ROMS in their own modules.
        # Wired here in Task 11+.
        from src.mcp.netcdf_reader.conventions import cf as _cf
        return _cf.detect(ds, attrs)
```

(Note: `paths.multi_file` and `conventions.cf` don't exist yet — the imports will fail at runtime if those code paths are hit. Task 11 fills `cf.py`; Task 31 fills `multi_file.py`. The single-file open path works without them.)

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_adapter.py -v
```

Expected: 3 passed (adapter contract + claims + single-file open).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/adapter.py \
        tests/mcp/netcdf-reader/unit/test_adapter.py
git commit -m "adapter: NetCDFAdapter + FormatAdapter Protocol skeleton"
```

---

### Task 10: CF convention detection — primary signal

**Files:**
- Create: `src/mcp/netcdf-reader/conventions/cf.py`
- Create: `tests/mcp/netcdf-reader/unit/test_conventions_cf.py`

- [ ] **Step 1: Write failing test for `detect()`**

```python
# tests/mcp/netcdf-reader/unit/test_conventions_cf.py
import xarray as xr
from src.mcp.netcdf_reader.conventions.cf import detect


def test_detect_cf_from_global_attr(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    result = detect(ds, ds.attrs)
    assert result["primary"] == "CF"
    assert result["confidence"] == "high"
    assert any("Conventions" in e for e in result["evidence"])
    assert result["candidates"] is None
    ds.close()


def test_detect_no_conventions_attr(tmp_path):
    # File without Conventions attr — low confidence, candidates list
    import numpy as np
    ds = xr.Dataset({"x": (("y",), np.array([1, 2, 3]))})
    p = tmp_path / "blank.nc"
    ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result["primary"] in ("CF", "unknown")
    if result["primary"] == "unknown":
        assert result["candidates"] is not None
    ds2.close()


def test_detect_cmip_from_mip_era(tmp_path):
    import numpy as np
    ds = xr.Dataset(
        {"tas": (("time", "lat", "lon"),
                 np.zeros((1, 2, 2), dtype="float32"))},
        attrs={"Conventions": "CF-1.7", "mip_era": "CMIP6", "experiment_id": "historical"},
    )
    p = tmp_path / "cmip.nc"
    ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result["primary"] == "CMIP"
    assert any("mip_era" in e for e in result["evidence"])
    ds2.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_cf.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `cf.py` — detection only**

```python
# src/mcp/netcdf-reader/conventions/cf.py
"""⤴ format-agnostic — eligible for _core/ lift.

CF (and CF-derived: CMIP) detection. WRF/ROMS detection lives in
conventions/wrf.py and conventions/roms.py respectively. This module
detects CF-family conventions and extracts CF-defined metadata
(time, spatial, vertical coords).
"""
from __future__ import annotations

from typing import Any

import xarray as xr


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
    evidence: list[str] = []
    primary = "unknown"
    confidence = "low"

    conv = attrs.get("Conventions", "")
    if isinstance(conv, str) and conv.upper().startswith("CF"):
        primary = "CF"
        confidence = "high"
        evidence.append(f"Conventions attr = {conv!r}")

    if "mip_era" in attrs or "cmor_version" in attrs:
        # CMIP files always have Conventions=CF-1.x AND mip_era / cmor_version
        primary = "CMIP"
        confidence = "high"
        if "mip_era" in attrs:
            evidence.append(f"mip_era attr = {attrs['mip_era']!r}")
        if "cmor_version" in attrs:
            evidence.append(f"cmor_version attr = {attrs['cmor_version']!r}")

    candidates = None
    if primary == "unknown":
        # Soft signals: presence of standard_name on at least one variable
        soft_evidence = []
        for vname, var in ds.data_vars.items():
            if "standard_name" in var.attrs:
                soft_evidence.append(f"{vname} has standard_name attr")
                break
        if soft_evidence:
            primary = "CF"
            confidence = "low"
            evidence.extend(soft_evidence)
            candidates = [
                {"convention": "CF", "confidence": 0.5, "evidence": soft_evidence},
                {"convention": "unknown", "confidence": 0.5, "evidence": []},
            ]

    return {
        "primary": primary,
        "confidence": confidence,
        "evidence": evidence,
        "candidates": candidates,
    }
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_cf.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/cf.py \
        tests/mcp/netcdf-reader/unit/test_conventions_cf.py
git commit -m "conventions/cf: primary detection (CF, CMIP)"
```

---

### Task 11: CF — variable, time, spatial, vertical extraction

**Files:**
- Modify: `src/mcp/netcdf-reader/conventions/cf.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_conventions_cf.py`

- [ ] **Step 1: Append failing tests for extraction**

```python
# Append to tests/mcp/netcdf-reader/unit/test_conventions_cf.py
from src.mcp.netcdf_reader.conventions.cf import (
    extract_variables, extract_time, extract_spatial, extract_vertical,
)


def test_extract_variables_includes_long_name_units(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    vars_out = extract_variables(ds)
    assert len(vars_out) == 1
    v = vars_out[0]
    assert v["name"] == "ta"
    assert v["long_name"] == "Air Temperature"
    assert v["units"] == "K"
    assert v["standard_name"] == "air_temperature"
    assert v["dims"] == ["time", "plev", "lat", "lon"]
    assert v["shape"] == [3, 4, 19, 72]
    assert v["dtype"] == "float32"
    assert v["is_staggered"] is False
    ds.close()


def test_extract_time_basic(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    t = extract_time(ds)
    assert t["name"] == "time"
    assert t["n"] == 3
    assert t["monotonic"] == "increasing"
    assert t["calendar"] in ("standard", "proleptic_gregorian", "gregorian")
    assert t["range"][0].startswith("2024-09-01")
    ds.close()


def test_extract_spatial_rectilinear_360_convention(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    s = extract_spatial(ds)
    assert s["coord_kind"] == "rectilinear"
    assert s["lat_name"] == "lat"
    assert s["lon_name"] == "lon"
    assert s["lon_convention"] == "0..360"
    ds.close()


def test_extract_spatial_neg180_convention(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    s = extract_spatial(ds)
    assert s["lon_convention"] == "-180..180"
    ds.close()


def test_extract_vertical_pressure_levels(cf_4d_file):
    ds = xr.open_dataset(cf_4d_file)
    v = extract_vertical(ds)
    assert v["name"] == "plev"
    assert v["kind"] == "pressure"
    assert v["n"] == 4
    assert v["monotonic"] == "decreasing"
    ds.close()


def test_extract_vertical_none_for_3d(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert extract_vertical(ds) is None
    ds.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_cf.py -v
```

Expected: extraction tests fail with `ImportError`.

- [ ] **Step 3: Append extraction functions to `cf.py`**

```python
# Append to src/mcp/netcdf-reader/conventions/cf.py

import numpy as np

_LAT_NAMES = ("lat", "latitude", "y", "rlat", "nav_lat")
_LON_NAMES = ("lon", "longitude", "x", "rlon", "nav_lon")
_TIME_NAMES = ("time", "Time", "T", "ocean_time")


def extract_variables(ds: xr.Dataset) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, da in ds.data_vars.items():
        is_stag = any("stag" in d.lower() for d in da.dims)
        out.append({
            "name": str(name),
            "long_name": da.attrs.get("long_name"),
            "standard_name": da.attrs.get("standard_name"),
            "description": da.attrs.get("description"),
            "units": da.attrs.get("units"),
            "dims": [str(d) for d in da.dims],
            "shape": list(da.shape),
            "dtype": str(da.dtype),
            "grid_kind": "scalar",
            "is_staggered": is_stag,
        })
    return out


def _find_coord(ds: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    for n in candidates:
        if n in ds.coords or n in ds.dims:
            return n
    return None


def extract_time(ds: xr.Dataset) -> dict[str, Any] | None:
    name = _find_coord(ds, _TIME_NAMES)
    if name is None:
        return None
    coord = ds[name]
    values = coord.values
    n = len(values)
    if n == 0:
        return {"name": name, "n": 0, "calendar": "unknown",
                "range": [], "step": None, "monotonic": "unknown"}
    diffs = np.diff(values) if n > 1 else None
    if diffs is None or len(diffs) == 0:
        monotonic = "unknown"
    elif np.all(diffs > np.timedelta64(0, "ns")):
        monotonic = "increasing"
    elif np.all(diffs < np.timedelta64(0, "ns")):
        monotonic = "decreasing"
    else:
        monotonic = "non-monotonic"
    # Calendar — xarray sets it on the coord's encoding or attrs
    calendar = coord.encoding.get("calendar") or coord.attrs.get("calendar") or "standard"
    # Step (uniform diff if all equal)
    step = None
    if diffs is not None and len(diffs) > 0:
        if np.all(diffs == diffs[0]):
            step = _timedelta_to_iso(diffs[0])
    return {
        "name": name,
        "n": n,
        "calendar": str(calendar),
        "range": [_dt_to_iso(values[0]), _dt_to_iso(values[-1])],
        "step": step,
        "monotonic": monotonic,
    }


def _dt_to_iso(v: Any) -> str:
    return np.datetime_as_string(v, unit="s") if hasattr(v, "astype") else str(v)


def _timedelta_to_iso(td: np.timedelta64) -> str:
    seconds = int(td / np.timedelta64(1, "s"))
    if seconds % 86400 == 0:
        return f"P{seconds // 86400}D"
    if seconds % 3600 == 0:
        return f"PT{seconds // 3600}H"
    if seconds % 60 == 0:
        return f"PT{seconds // 60}M"
    return f"PT{seconds}S"


def extract_spatial(ds: xr.Dataset) -> dict[str, Any] | None:
    lat_name = _find_coord(ds, _LAT_NAMES)
    lon_name = _find_coord(ds, _LON_NAMES)
    if lat_name is None or lon_name is None:
        return None
    lat = ds[lat_name]
    lon = ds[lon_name]
    coord_kind = "rectilinear" if lat.ndim == 1 and lon.ndim == 1 else "curvilinear"
    lon_min = float(lon.min())
    lon_max = float(lon.max())
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"
    return {
        "coord_kind": coord_kind,
        "lat_name": lat_name,
        "lon_name": lon_name,
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": lon_convention,
    }


_VERTICAL_KINDS = {
    "plev": "pressure", "lev": "model_level", "level": "model_level",
    "altitude": "height", "z": "height",
    "bottom_top": "eta", "bottom_top_stag": "eta",
    "s_rho": "sigma", "s_w": "sigma",
}


def extract_vertical(ds: xr.Dataset) -> dict[str, Any] | None:
    for cand_name, kind in _VERTICAL_KINDS.items():
        if cand_name in ds.coords or cand_name in ds.dims:
            coord = ds[cand_name] if cand_name in ds.coords else None
            n = ds.sizes[cand_name]
            if coord is None or n == 0:
                return {"name": cand_name, "kind": kind, "units": None,
                        "n": n, "monotonic": "unknown"}
            values = coord.values
            diffs = np.diff(values) if n > 1 else None
            if diffs is None or len(diffs) == 0:
                monotonic = "unknown"
            elif np.all(diffs > 0):
                monotonic = "increasing"
            elif np.all(diffs < 0):
                monotonic = "decreasing"
            else:
                monotonic = "non-monotonic"
            return {
                "name": cand_name,
                "kind": kind,
                "units": coord.attrs.get("units"),
                "n": int(n),
                "monotonic": monotonic,
            }
    return None
```

- [ ] **Step 4: Verify all CF tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_cf.py -v
```

Expected: 9 passed (3 from Task 10 + 6 new).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/cf.py \
        tests/mcp/netcdf-reader/unit/test_conventions_cf.py
git commit -m "conventions/cf: variable/time/spatial/vertical extraction"
```

---

## Phase 3: First end-to-end tool — `inspect()`

End of phase: `inspect(path)` works on a synthetic CF file end-to-end, with cache hit/miss verified.

### Task 12: `inspect()` tool

**Files:**
- Create: `src/mcp/netcdf-reader/tools/inspect.py`
- Create: `tests/mcp/netcdf-reader/unit/test_inspect.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_inspect.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def test_inspect_cf_4d_returns_success_envelope(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(cf_4d_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_single"
    assert r["files"] == [str(cf_4d_file)]
    assert r["convention"]["primary"] == "CF"
    var_names = [v["name"] for v in r["variables"]]
    assert "ta" in var_names
    assert r["time"]["n"] == 3
    assert r["spatial"]["coord_kind"] == "rectilinear"
    assert r["vertical"]["kind"] == "pressure"


def test_inspect_uses_cache_on_second_call(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env1 = inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    # Second call should return same payload — and we can detect cache by
    # checking that the cache file exists.
    cache_dir = tmp_path / ".ncplot" / "inspections"
    assert cache_dir.exists()
    files = list(cache_dir.glob("*.json"))
    assert len(files) == 1
    env2 = inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    assert env1["result"] == env2["result"]


def test_inspect_invalidates_cache_on_mtime_change(cf_3d_file, tmp_path, monkeypatch):
    import os, time
    monkeypatch.chdir(tmp_path)
    inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    cache_dir = tmp_path / ".ncplot" / "inspections"
    files_before = sorted(cache_dir.glob("*.json"))
    time.sleep(0.01)
    os.utime(cf_3d_file, None)
    inspect(str(cf_3d_file), adapter=NetCDFAdapter())
    files_after = sorted(cache_dir.glob("*.json"))
    # Different mtime → different hash → new cache entry, old still present
    assert len(files_after) == 2


def test_inspect_missing_file_returns_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(tmp_path / "no.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is False
    # ClassifyError converted to file_not_found
    assert env["error"]["code"] in ("file_not_found", "unsupported_path_scheme")
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_inspect.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/inspect.py`**

```python
# src/mcp/netcdf-reader/tools/inspect.py
"""⤴ format-agnostic — eligible for _core/ lift.

inspect() — full metadata summary of a file or multi-file dataset.
Cached at .ncplot/inspections/<hash>.json with mtime-based invalidation.
"""
from __future__ import annotations

from typing import Any

from src.mcp.netcdf_reader import cache, envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.conventions import cf as _cf
from src.mcp.netcdf_reader.paths.classify import (
    ClassifyError, PathKind, classify,
)


def inspect(path: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    try:
        cls = classify(path)
    except ClassifyError as e:
        # Distinguish "doesn't exist" from "unsupported scheme"
        msg = str(e)
        code = (envelope.ErrorCode.UNSUPPORTED_PATH_SCHEME
                if "unsupported scheme" in msg or "malformed" in msg
                else envelope.ErrorCode.FILE_NOT_FOUND)
        return envelope.error(code, msg, context={"path": path})

    is_remote = cls.kind in (PathKind.REMOTE_URL, PathKind.SSH_REMOTE)
    key = cache.inspection_key(cls.paths or [path], remote=is_remote)
    cached = cache.read_inspection(key)
    if cached is not None:
        return envelope.success(cached)

    try:
        ds = adapter.open(cls.paths)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"path": path})

    try:
        attrs = dict(ds.attrs)
        convention = adapter.detect_conventions(ds, attrs)
        result = {
            "path": cls.raw,
            "kind": cls.kind,
            "files": cls.paths,
            "convention": convention,
            "variables": _cf.extract_variables(ds),
            "time": _cf.extract_time(ds),
            "spatial": _cf.extract_spatial(ds),
            "vertical": _cf.extract_vertical(ds),
            "dims": {str(k): int(v) for k, v in ds.sizes.items()},
            "attrs": {k: _safe(v) for k, v in attrs.items()},
        }
    finally:
        ds.close()

    cache.write_inspection(key, result)
    return envelope.success(result)


def _safe(v: Any) -> Any:
    """Coerce attr value to JSON-safe scalar."""
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_inspect.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/inspect.py \
        tests/mcp/netcdf-reader/unit/test_inspect.py
git commit -m "tools/inspect: end-to-end CF + cache + invalidation"
```

---

### Task 13: Phase-3 lint and integration smoke

**Files:**
- (no new files)

- [ ] **Step 1: Run all unit tests across the package**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: all green (~50 tests).

- [ ] **Step 2: Run ruff and mypy**

```bash
ruff check src/mcp/netcdf-reader/ tests/mcp/netcdf-reader/
mypy src/mcp/netcdf-reader/
```

Fix any issues.

- [ ] **Step 3: Hand-smoke the inspect tool from a Python REPL**

```bash
python -c "
import xarray as xr, numpy as np
from pathlib import Path
ds = xr.Dataset(
    {'tos': (('time','lat','lon'), np.zeros((2,3,4),dtype='float32'))},
    coords={'time': np.array(['2024-09-01','2024-09-02'], dtype='datetime64[D]'),
            'lat': np.array([0,1,2], dtype='float32'),
            'lon': np.array([0,1,2,3], dtype='float32')},
    attrs={'Conventions':'CF-1.7'},
)
ds.to_netcdf('/tmp/smoke.nc')
from src.mcp.netcdf_reader.tools.inspect import inspect
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
import json; print(json.dumps(inspect('/tmp/smoke.nc', adapter=NetCDFAdapter()), indent=2, default=str))
"
```

Expected: a success envelope with `result.convention.primary == "CF"`, `result.variables[0].name == "tos"`.

- [ ] **Step 4: Commit any cleanups**

```bash
git add -A
git diff --cached --quiet || git commit -m "phase-3 lint/typecheck pass"
```

---

## Phase 4: D/C-path tools — `resolve_spec`, `read_slice`, `compute_stats`, `peek`

End of phase: full set of single-file C-path and D-path tools work against synthetic CF fixtures. SSH/multi-file/WRF still pending; CF-only is end-to-end usable.

### Task 14: `resolve_spec()` — selectors → normalized spec

**Files:**
- Create: `src/mcp/netcdf-reader/tools/resolve_spec.py`
- Create: `tests/mcp/netcdf-reader/unit/test_resolve_spec.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_resolve_spec.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def test_resolve_spec_exact_time(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T06:00:00",
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is True
    r = env["result"]
    assert r["variable"] == "ta"
    assert r["resolved"]["time_match"] == "exact"
    assert r["resolved"]["time_index"] == 1


def test_resolve_spec_nearest_time_returns_match_kind(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T07:00:00",  # not exact — nearest is 06:00
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert r["resolved"]["time_match"] in ("nearest", "previous")


def test_resolve_spec_unknown_variable_returns_ambiguous(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="not_a_var",
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "variable"
    assert len(env["error"]["candidates"]) >= 1


def test_resolve_spec_lat_lon_bbox(cf_3d_file):
    env = resolve_spec(
        str(cf_3d_file), variable="tos",
        lat=[20, 50], lon=[100, 200],
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert "lat_indices" in r["resolved"]
    assert "lon_indices" in r["resolved"]
    assert r["slice_shape"][0] >= 1


def test_resolve_spec_level_on_3d_returns_not_4d(cf_3d_file):
    env = resolve_spec(
        str(cf_3d_file), variable="tos",
        level=500,
        adapter=NetCDFAdapter(),
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "not_4d"


def test_resolve_spec_estimates_bytes(cf_4d_file):
    env = resolve_spec(
        str(cf_4d_file), variable="ta",
        time="2024-09-01T00",
        adapter=NetCDFAdapter(),
    )
    r = env["result"]
    assert r["estimated_bytes"] > 0
    assert r["slice_shape"][0] == 1  # one time step
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_resolve_spec.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/resolve_spec.py`**

```python
# src/mcp/netcdf-reader/tools/resolve_spec.py
"""⤴ format-agnostic — eligible for _core/ lift.

resolve_spec() — validate and normalize a slice spec without reading
array values. Returns the spec the renderer (cycle 2) consumes.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope, selectors
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify


def _close_matches(name: str, names: list[str], k: int = 3) -> list[str]:
    import difflib
    return difflib.get_close_matches(name, names, n=k, cutoff=0.0)


def resolve_spec(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    regrid: str | None = None,
    adapter: FormatAdapter,
) -> dict[str, Any]:
    try:
        cls = classify(path)
    except ClassifyError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})

    try:
        ds = adapter.open(cls.paths)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND, str(e),
                              context={"path": path})

    try:
        if variable not in ds.data_vars:
            close = _close_matches(variable, [str(n) for n in ds.data_vars])
            return envelope.ambiguous(
                "variable",
                f"unknown variable: {variable!r}",
                candidates=[
                    {"value": c, "label": c,
                     "long_name": ds[c].attrs.get("long_name"),
                     "units": ds[c].attrs.get("units"),
                     "evidence": ["string-distance match"], "confidence": 0.5,
                     "param": "variable", "sensitive": False}
                    for c in close
                ] or [{"value": str(n), "label": str(n),
                       "long_name": ds[n].attrs.get("long_name"),
                       "units": ds[n].attrs.get("units"),
                       "evidence": [], "confidence": 0.1,
                       "param": "variable", "sensitive": False}
                      for n in list(ds.data_vars)[:5]],
                prompt=f"No variable named {variable!r}. Did you mean one of these?",
                retry_with_param="variable",
                context={"available": [str(n) for n in ds.data_vars]},
            )

        da = ds[variable]
        resolved: dict[str, Any] = {}
        notes: list[str] = []
        applied: list[dict[str, Any]] = []

        # --- time ---
        if time is not None:
            t_sel = selectors.parse_time(time)
            t_dim = next((d for d in da.dims if d in ("time", "Time", "ocean_time")), None)
            if t_dim is None:
                return envelope.error("internal_error",
                                      f"variable {variable} has no time dim", context={})
            tcoord = ds[t_dim].values
            if t_sel.kind == "iso":
                target = np.datetime64(t_sel.value)
                # Find exact or nearest
                if target in tcoord:
                    idx = int(np.where(tcoord == target)[0][0])
                    resolved["time_match"] = "exact"
                else:
                    diffs = np.abs(tcoord - target)
                    idx = int(np.argmin(diffs))
                    resolved["time_match"] = "nearest"
                resolved["time_index"] = idx
                resolved["time_value"] = str(tcoord[idx])
                notes.append(f"time matched {resolved['time_match']}")
            elif t_sel.kind == "sentinel":
                idx = 0 if t_sel.value == "first" else len(tcoord) - 1
                resolved["time_index"] = idx
                resolved["time_value"] = str(tcoord[idx])
                resolved["time_match"] = "exact"
            elif t_sel.kind == "index":
                resolved["time_index"] = t_sel.value
                resolved["time_value"] = str(tcoord[t_sel.value])
                resolved["time_match"] = "exact"

        # --- level ---
        if level is not None:
            v_dim = next((d for d in da.dims
                          if d in ("plev", "lev", "level", "altitude", "z",
                                   "bottom_top", "s_rho", "s_w")), None)
            if v_dim is None:
                return envelope.error(envelope.ErrorCode.NOT_4D,
                                      f"variable {variable} has no vertical dim",
                                      context={"dims": list(da.dims)})
            l_sel = selectors.parse_level(level)
            lcoord = ds[v_dim].values
            if l_sel.kind == "numeric":
                idx = int(np.argmin(np.abs(lcoord - l_sel.value)))
                resolved["level_index"] = idx
                resolved["level_value"] = float(lcoord[idx])
            elif l_sel.kind == "sentinel":
                # surface = lowest pressure-axis convention; for plev that's max
                if l_sel.value == "surface":
                    idx = int(np.argmax(lcoord)) if v_dim == "plev" else 0
                else:  # top
                    idx = int(np.argmin(lcoord)) if v_dim == "plev" else len(lcoord) - 1
                resolved["level_index"] = idx
                resolved["level_value"] = float(lcoord[idx])

        # --- lat/lon ---
        lat_dim = next((d for d in da.dims if d in ("lat", "latitude", "y")), None)
        lon_dim = next((d for d in da.dims if d in ("lon", "longitude", "x")), None)
        if lat is not None and lat_dim:
            lat_sel = selectors.parse_latlon(lat)
            lat_v = ds[lat_dim].values
            if lat_sel.kind == "bbox":
                lo, hi = lat_sel.value
                mask = (lat_v >= lo) & (lat_v <= hi)
                idxs = np.where(mask)[0]
                if len(idxs) == 0:
                    return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                          f"no lat values in {lat_sel.value}",
                                          context={})
                resolved["lat_indices"] = [int(idxs[0]), int(idxs[-1])]
            elif lat_sel.kind == "point":
                idx = int(np.argmin(np.abs(lat_v - lat_sel.value)))
                resolved["lat_index"] = idx
        if lon is not None and lon_dim:
            lon_sel = selectors.parse_latlon(lon)
            lon_v = ds[lon_dim].values
            if lon_sel.kind == "bbox":
                lo, hi = lon_sel.value
                mask = (lon_v >= lo) & (lon_v <= hi)
                idxs = np.where(mask)[0]
                if len(idxs) == 0:
                    return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                          f"no lon values in {lon_sel.value}",
                                          context={})
                resolved["lon_indices"] = [int(idxs[0]), int(idxs[-1])]
            elif lon_sel.kind == "point":
                idx = int(np.argmin(np.abs(lon_v - lon_sel.value)))
                resolved["lon_index"] = idx

        # Compute slice shape and bytes estimate
        shape: list[int] = []
        for d in da.dims:
            if d in ("time", "Time", "ocean_time") and "time_index" in resolved:
                shape.append(1)
            elif d in ("plev", "lev", "level", "bottom_top") and "level_index" in resolved:
                shape.append(1)
            elif d in ("lat", "latitude", "y") and "lat_indices" in resolved:
                lo, hi = resolved["lat_indices"]
                shape.append(hi - lo + 1)
            elif d in ("lat", "latitude", "y") and "lat_index" in resolved:
                shape.append(1)
            elif d in ("lon", "longitude", "x") and "lon_indices" in resolved:
                lo, hi = resolved["lon_indices"]
                shape.append(hi - lo + 1)
            elif d in ("lon", "longitude", "x") and "lon_index" in resolved:
                shape.append(1)
            else:
                shape.append(int(ds.sizes[d]))

        itemsize = da.dtype.itemsize
        nbytes = itemsize
        for s in shape:
            nbytes *= s

        if regrid == "to_centers":
            applied.append({"kind": "regrid_to_centers"})

        spec = {
            "path": cls.raw,
            "variable": variable,
            "selectors": {
                "time": time, "level": level, "lat": lat, "lon": lon,
                "region": region, "regrid": regrid,
            },
            "resolved": resolved,
            "slice_shape": shape,
            "estimated_bytes": int(nbytes),
            "applied_transforms": applied,
            "notes": notes,
        }
        return envelope.success(spec)
    finally:
        ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_resolve_spec.py -v
```

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/resolve_spec.py \
        tests/mcp/netcdf-reader/unit/test_resolve_spec.py
git commit -m "tools/resolve_spec: selectors → normalized spec"
```

---

### Task 15: `read_slice()` — inline form

**Files:**
- Create: `src/mcp/netcdf-reader/tools/read_slice.py`
- Create: `tests/mcp/netcdf-reader/unit/test_read_slice.py`

- [ ] **Step 1: Write failing tests for inline form only**

```python
# tests/mcp/netcdf-reader/unit/test_read_slice.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.read_slice import read_slice


def test_read_slice_inline_small(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_3d_file), variable="tos",
        time="2024-09-01",
        lat=[0, 5], lon=[0, 5],
        adapter=NetCDFAdapter(),
        max_inline_bytes=100_000,
    )
    assert env["ok"] is True
    r = env["result"]
    assert r["form"] == "inline"
    assert "values" in r
    assert "coords" in r
    assert "stats" in r
    assert r["units"] == "K"
    assert r["stats"]["fraction_nan"] == 0.0


def test_read_slice_inline_nan_serialization(tmp_path, monkeypatch):
    import xarray as xr
    import numpy as np
    monkeypatch.chdir(tmp_path)
    arr = np.array([[[1.0, np.nan]]], dtype="float32")
    ds = xr.Dataset(
        {"v": (("time", "lat", "lon"), arr)},
        coords={"time": np.array(["2024-01-01"], dtype="datetime64[D]"),
                "lat": [0.0], "lon": [0.0, 1.0]},
        attrs={"Conventions": "CF-1.7"},
    )
    p = tmp_path / "nan.nc"; ds.to_netcdf(p)
    env = read_slice(str(p), variable="v", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["stats"]["fraction_nan"] == 0.5
    # NaN serialized as the string "NaN"
    flat = str(r["values"])
    assert "NaN" in flat


def test_read_slice_size_limit_exceeded(cf_4d_file, tmp_path, monkeypatch):
    # Force a very small inline cap so the full slice exceeds it
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_4d_file), variable="ta",
        adapter=NetCDFAdapter(),
        max_inline_bytes=100,  # tiny
    )
    # Will trigger file-form path (Task 16). For Task 15 we expect
    # size_limit_exceeded if file form not implemented yet.
    # After Task 16 lands, this becomes form == "file".
    # Skip until file form is implemented:
    import pytest
    pytest.skip("file form lands in Task 16")
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_read_slice.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/read_slice.py` — inline form only**

```python
# src/mcp/netcdf-reader/tools/read_slice.py
"""⤴ format-agnostic — eligible for _core/ lift.

read_slice() — hybrid output. Inline JSON for small slices; file path
for large slices (Task 16 adds the file-form branch).
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import ClassifyError, classify
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def _to_json_safe(arr: np.ndarray) -> Any:
    """Convert ndarray to nested list with NaN → 'NaN'."""
    out: list[Any] = []
    if arr.ndim == 0:
        v = arr.item()
        return "NaN" if isinstance(v, float) and np.isnan(v) else v
    for sub in arr:
        out.append(_to_json_safe(np.asarray(sub)))
    return out


def _apply_selectors(da, resolved: dict[str, Any]):
    """Apply resolved selectors to an xarray DataArray."""
    sel: dict[str, Any] = {}
    isel: dict[str, Any] = {}
    if "time_index" in resolved:
        for d in da.dims:
            if d in ("time", "Time", "ocean_time"):
                isel[d] = resolved["time_index"]
                break
    if "level_index" in resolved:
        for d in da.dims:
            if d in ("plev", "lev", "level", "bottom_top"):
                isel[d] = resolved["level_index"]
                break
    if "lat_indices" in resolved:
        for d in da.dims:
            if d in ("lat", "latitude", "y"):
                lo, hi = resolved["lat_indices"]
                isel[d] = slice(lo, hi + 1)
                break
    if "lat_index" in resolved:
        for d in da.dims:
            if d in ("lat", "latitude", "y"):
                isel[d] = resolved["lat_index"]
                break
    if "lon_indices" in resolved:
        for d in da.dims:
            if d in ("lon", "longitude", "x"):
                lo, hi = resolved["lon_indices"]
                isel[d] = slice(lo, hi + 1)
                break
    if "lon_index" in resolved:
        for d in da.dims:
            if d in ("lon", "longitude", "x"):
                isel[d] = resolved["lon_index"]
                break
    return da.isel(**isel)


def read_slice(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    regrid: str | None = None,
    max_inline_bytes: int = 100_000,
    adapter: FormatAdapter,
) -> dict[str, Any]:
    spec_env = resolve_spec(
        path, variable, time=time, level=level, lat=lat, lon=lon,
        region=region, regrid=regrid, adapter=adapter,
    )
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]
    estimated = int(spec["estimated_bytes"])

    if estimated > max_inline_bytes:
        # File-form lands in Task 16. Until then, return size_limit_exceeded.
        return envelope.error(
            envelope.ErrorCode.SIZE_LIMIT_EXCEEDED,
            f"slice would be {estimated} bytes, exceeds {max_inline_bytes}",
            context={"estimated_bytes": estimated,
                     "max_inline_bytes": max_inline_bytes,
                     "shape": spec["slice_shape"]},
        )

    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        nan_count = int(np.isnan(values).sum()) if values.dtype.kind == "f" else 0
        total = int(values.size)
        stats = {
            "min": float(np.nanmin(values)) if values.dtype.kind == "f" else float(values.min()),
            "max": float(np.nanmax(values)) if values.dtype.kind == "f" else float(values.max()),
            "mean": float(np.nanmean(values)) if values.dtype.kind == "f" else float(values.mean()),
            "fraction_nan": nan_count / total if total else 0.0,
        }
        coords_out: dict[str, list[Any]] = {}
        for d in da.dims:
            if d in da.coords:
                coords_out[str(d)] = _to_json_safe(np.asarray(da[d].values))
        result = {
            "form": "inline",
            "values": _to_json_safe(values),
            "coords": coords_out,
            "dims": [str(d) for d in da.dims],
            "shape": list(values.shape),
            "units": ds[variable].attrs.get("units"),
            "stats": stats,
        }
        return envelope.success(result)
    finally:
        ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_read_slice.py -v
```

Expected: 2 passed, 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/read_slice.py \
        tests/mcp/netcdf-reader/unit/test_read_slice.py
git commit -m "tools/read_slice: inline form with NaN serialization"
```

---

### Task 16: `read_slice()` — file form (session-scoped temp)

**Files:**
- Modify: `src/mcp/netcdf-reader/tools/read_slice.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_read_slice.py`

- [ ] **Step 1: Replace the skipped test with a real one and add new tests**

```python
# Replace test_read_slice_size_limit_exceeded in
# tests/mcp/netcdf-reader/unit/test_read_slice.py with:

def test_read_slice_file_form_when_above_threshold(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_4d_file), variable="ta",
        adapter=NetCDFAdapter(),
        max_inline_bytes=100,
    )
    assert env["ok"] is True
    r = env["result"]
    assert r["form"] == "file"
    assert r["path"].endswith(".nc")
    assert r["format"] == "netcdf"
    assert r["size_bytes"] > 0
    # The temp file should exist on disk
    from pathlib import Path
    assert Path(r["path"]).exists()


def test_read_slice_file_form_dir_under_session(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = read_slice(
        str(cf_4d_file), variable="ta",
        adapter=NetCDFAdapter(),
        max_inline_bytes=100,
    )
    r = env["result"]
    assert ".ncplot/slices/" in r["path"]
```

- [ ] **Step 2: Run — file-form tests fail**

```bash
pytest tests/mcp/netcdf-reader/unit/test_read_slice.py -v -k file_form
```

Expected: 2 failures (size_limit_exceeded was returned; we need form == "file").

- [ ] **Step 3: Add session-scope helper and file-form branch**

In `read_slice.py`, replace the `if estimated > max_inline_bytes` branch:

```python
# Add at module top:
import hashlib
import json
import os
import time as _time
from pathlib import Path

_SESSION_ID: str | None = None


def _session_id() -> str:
    global _SESSION_ID
    if _SESSION_ID is None:
        _SESSION_ID = f"pid{os.getpid()}-{int(_time.time())}"
    return _SESSION_ID


def _slice_dir() -> Path:
    d = Path.cwd() / ".ncplot" / "slices" / _session_id()
    d.mkdir(parents=True, exist_ok=True)
    return d


def _slice_hash(spec: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(json.dumps({
        "path": spec["path"],
        "variable": spec["variable"],
        "resolved": spec["resolved"],
        "applied_transforms": spec["applied_transforms"],
    }, sort_keys=True, default=str).encode("utf-8"))
    return h.hexdigest()[:16]
```

Replace the `if estimated > max_inline_bytes` branch with:

```python
    if estimated > max_inline_bytes:
        cls = classify(path)
        ds = adapter.open(cls.paths)
        try:
            da = _apply_selectors(ds[variable], spec["resolved"])
            sliced = da.load()
            out_path = _slice_dir() / f"{_slice_hash(spec)}.nc"
            sliced.to_netcdf(out_path)
            values = sliced.values
            nan_count = int(np.isnan(values).sum()) if values.dtype.kind == "f" else 0
            total = int(values.size)
            stats = {
                "min": float(np.nanmin(values)) if values.dtype.kind == "f" else float(values.min()),
                "max": float(np.nanmax(values)) if values.dtype.kind == "f" else float(values.max()),
                "mean": float(np.nanmean(values)) if values.dtype.kind == "f" else float(values.mean()),
                "fraction_nan": nan_count / total if total else 0.0,
            }
            coords_summary: dict[str, dict[str, Any]] = {}
            for d in sliced.dims:
                if d in sliced.coords:
                    cv = np.asarray(sliced[d].values)
                    coords_summary[str(d)] = {
                        "n": int(cv.size),
                        "range": [_to_json_safe(cv.min()), _to_json_safe(cv.max())],
                    }
            result = {
                "form": "file",
                "path": str(out_path),
                "format": "netcdf",
                "size_bytes": out_path.stat().st_size,
                "dims": [str(d) for d in sliced.dims],
                "shape": list(values.shape),
                "coords_summary": coords_summary,
                "units": ds[variable].attrs.get("units"),
                "stats": stats,
            }
            return envelope.success(result)
        finally:
            ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_read_slice.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/read_slice.py \
        tests/mcp/netcdf-reader/unit/test_read_slice.py
git commit -m "tools/read_slice: file form with session-scoped temp"
```

---

### Task 17: Slice cache cleanup at startup

**Files:**
- Create: `src/mcp/netcdf-reader/lifecycle.py`
- Create: `tests/mcp/netcdf-reader/unit/test_lifecycle.py`

- [ ] **Step 1: Write failing test**

```python
# tests/mcp/netcdf-reader/unit/test_lifecycle.py
from pathlib import Path
from src.mcp.netcdf_reader.lifecycle import cleanup_old_slice_dirs


def test_cleanup_removes_old_session_dirs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".ncplot" / "slices"
    (base / "pid-old-1").mkdir(parents=True)
    (base / "pid-old-1" / "x.nc").write_bytes(b"x")
    (base / "pid-old-2").mkdir()
    cleanup_old_slice_dirs(keep="pid-current")
    assert not (base / "pid-old-1").exists()
    assert not (base / "pid-old-2").exists()


def test_cleanup_keeps_current(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    base = tmp_path / ".ncplot" / "slices"
    (base / "pid-current").mkdir(parents=True)
    (base / "pid-current" / "x.nc").write_bytes(b"x")
    cleanup_old_slice_dirs(keep="pid-current")
    assert (base / "pid-current" / "x.nc").exists()


def test_cleanup_handles_missing_base(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cleanup_old_slice_dirs(keep="any")  # should not raise
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_lifecycle.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `lifecycle.py`**

```python
# src/mcp/netcdf-reader/lifecycle.py
"""⤴ format-agnostic — eligible for _core/ lift.

Lifecycle hooks. cleanup_old_slice_dirs() runs at MCP server startup
and removes slice temp directories from previous sessions.
"""
from __future__ import annotations

import shutil
from pathlib import Path


def cleanup_old_slice_dirs(*, keep: str) -> None:
    base = Path.cwd() / ".ncplot" / "slices"
    if not base.exists():
        return
    for child in base.iterdir():
        if child.is_dir() and child.name != keep:
            shutil.rmtree(child, ignore_errors=True)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_lifecycle.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/lifecycle.py \
        tests/mcp/netcdf-reader/unit/test_lifecycle.py
git commit -m "lifecycle: cleanup old slice dirs at startup"
```

---

### Task 18: `compute_stats()` — aggregate stats

**Files:**
- Create: `src/mcp/netcdf-reader/tools/compute_stats.py`
- Create: `tests/mcp/netcdf-reader/unit/test_compute_stats.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_compute_stats.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.compute_stats import compute_stats


def test_compute_stats_returns_required_fields(cf_3d_file):
    env = compute_stats(str(cf_3d_file), variable="tos", adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    for k in ("min", "max", "mean", "std", "count",
              "fraction_nan", "percentiles", "units", "shape_summarized"):
        assert k in r
    assert set(r["percentiles"].keys()) == {"p5", "p50", "p95"}


def test_compute_stats_numeric_correctness(tmp_path):
    import xarray as xr, numpy as np
    arr = np.arange(100, dtype="float32").reshape(10, 10)
    ds = xr.Dataset({"v": (("y", "x"), arr)},
                    attrs={"Conventions": "CF-1.7"})
    p = tmp_path / "x.nc"; ds.to_netcdf(p)
    env = compute_stats(str(p), variable="v", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["min"] == 0.0
    assert r["max"] == 99.0
    assert abs(r["mean"] - 49.5) < 1e-3
    assert r["count"] == 100
    assert r["fraction_nan"] == 0.0
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_compute_stats.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/compute_stats.py`**

```python
# src/mcp/netcdf-reader/tools/compute_stats.py
"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import classify
from src.mcp.netcdf_reader.tools.read_slice import _apply_selectors
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec


def compute_stats(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    region: str | None = None,
    adapter: FormatAdapter,
) -> dict[str, Any]:
    spec_env = resolve_spec(
        path, variable, time=time, level=level, lat=lat, lon=lon,
        region=region, adapter=adapter,
    )
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]

    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        is_float = values.dtype.kind == "f"
        nan_count = int(np.isnan(values).sum()) if is_float else 0
        total = int(values.size)
        if is_float:
            arr_clean = values[~np.isnan(values)]
        else:
            arr_clean = values
        if arr_clean.size == 0:
            return envelope.error(envelope.ErrorCode.EMPTY_SLICE,
                                  "no non-NaN values", context={})
        result = {
            "min": float(arr_clean.min()),
            "max": float(arr_clean.max()),
            "mean": float(arr_clean.mean()),
            "std": float(arr_clean.std()),
            "count": total,
            "fraction_nan": nan_count / total if total else 0.0,
            "percentiles": {
                "p5": float(np.percentile(arr_clean, 5)),
                "p50": float(np.percentile(arr_clean, 50)),
                "p95": float(np.percentile(arr_clean, 95)),
            },
            "units": ds[variable].attrs.get("units"),
            "shape_summarized": list(values.shape),
        }
        return envelope.success(result)
    finally:
        ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_compute_stats.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/compute_stats.py \
        tests/mcp/netcdf-reader/unit/test_compute_stats.py
git commit -m "tools/compute_stats: min/max/mean/std/percentiles 5/50/95"
```

---

### Task 19: `peek()` — single-point lookup with hard cap

**Files:**
- Create: `src/mcp/netcdf-reader/tools/peek.py`
- Create: `tests/mcp/netcdf-reader/unit/test_peek.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_peek.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.peek import peek, PEEK_HARD_CAP_BYTES


def test_peek_single_point(cf_3d_file):
    env = peek(str(cf_3d_file), variable="tos",
               time="2024-09-01", lat=10.0, lon=100.0,
               adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert "value" in r
    assert isinstance(r["value"], (int, float, str))
    assert r["units"] == "K"
    assert "distance_to_nearest" in r
    assert "lat_deg" in r["distance_to_nearest"]


def test_peek_refuses_when_exceeds_cap(cf_3d_file):
    # Whole-grid peek would exceed cap
    env = peek(str(cf_3d_file), variable="tos",
               time="2024-09-01",
               adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] == "size_limit_exceeded"
    assert env["error"]["context"]["cap"] == PEEK_HARD_CAP_BYTES
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_peek.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/peek.py`**

```python
# src/mcp/netcdf-reader/tools/peek.py
"""⤴ format-agnostic — eligible for _core/ lift.

peek() — single-point or tiny-area value lookup. Hard-capped at
PEEK_HARD_CAP_BYTES. Refuses larger requests with size_limit_exceeded.
"""
from __future__ import annotations

from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import classify
from src.mcp.netcdf_reader.tools.read_slice import _apply_selectors, _to_json_safe
from src.mcp.netcdf_reader.tools.resolve_spec import resolve_spec

PEEK_HARD_CAP_BYTES = 10_000


def peek(
    path: str,
    variable: str,
    *,
    time: Any = None,
    level: Any = None,
    lat: Any = None,
    lon: Any = None,
    adapter: FormatAdapter,
) -> dict[str, Any]:
    spec_env = resolve_spec(path, variable, time=time, level=level,
                             lat=lat, lon=lon, adapter=adapter)
    if not spec_env["ok"]:
        return spec_env
    spec = spec_env["result"]
    if spec["estimated_bytes"] > PEEK_HARD_CAP_BYTES:
        return envelope.error(
            envelope.ErrorCode.SIZE_LIMIT_EXCEEDED,
            f"peek refuses {spec['estimated_bytes']}-byte slice (cap {PEEK_HARD_CAP_BYTES})",
            context={"estimated_bytes": spec["estimated_bytes"],
                     "cap": PEEK_HARD_CAP_BYTES,
                     "shape": spec["slice_shape"]},
        )

    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        da = _apply_selectors(ds[variable], spec["resolved"])
        values = da.load().values
        coords_out: dict[str, Any] = {}
        dist: dict[str, Any] = {}
        for d in da.dims:
            if d in da.coords:
                cv = np.asarray(da[d].values)
                if cv.ndim == 0:
                    coords_out[str(d)] = _to_json_safe(cv)
                else:
                    coords_out[str(d)] = _to_json_safe(cv)
        # Distance-to-nearest only meaningful for point selectors
        if isinstance(lat, (int, float)) and "lat_index" in spec["resolved"]:
            actual = float(ds[next(d for d in ds[variable].dims
                                   if d in ("lat", "latitude", "y"))]
                           .values[spec["resolved"]["lat_index"]])
            dist["lat_deg"] = abs(actual - float(lat))
        if isinstance(lon, (int, float)) and "lon_index" in spec["resolved"]:
            actual = float(ds[next(d for d in ds[variable].dims
                                   if d in ("lon", "longitude", "x"))]
                           .values[spec["resolved"]["lon_index"]])
            dist["lon_deg"] = abs(actual - float(lon))

        result = {
            "value": _to_json_safe(values),
            "shape": list(values.shape),
            "coords": coords_out,
            "units": ds[variable].attrs.get("units"),
            "distance_to_nearest": dist,
        }
        return envelope.success(result)
    finally:
        ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_peek.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/peek.py \
        tests/mcp/netcdf-reader/unit/test_peek.py
git commit -m "tools/peek: single-point lookup with 10KB hard cap"
```

---

## Phase 5: Help tools — `find_variables` and `find_time`

End of phase: hint-based search tools work without skills (standalone-MCP usability).

### Task 20: `find_variables()` and `find_time()`

**Files:**
- Create: `src/mcp/netcdf-reader/tools/find.py`
- Create: `tests/mcp/netcdf-reader/unit/test_find.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_find.py
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.find import find_variables, find_time


def test_find_variables_long_name(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="temperature",
                         adapter=NetCDFAdapter())
    r = env["result"]
    assert len(r["matches"]) >= 1
    top = r["matches"][0]
    assert top["name"] == "ta"
    assert top["matched_field"] == "long_name"
    assert top["score"] > 0.0


def test_find_variables_standard_name(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="air_temperature",
                         adapter=NetCDFAdapter())
    top = env["result"]["matches"][0]
    assert top["name"] == "ta"
    assert top["matched_field"] == "standard_name"


def test_find_variables_unrelated_hint_returns_low_scores(cf_4d_file):
    env = find_variables(str(cf_4d_file), hint="quokka",
                         adapter=NetCDFAdapter())
    matches = env["result"]["matches"]
    if matches:
        assert matches[0]["score"] < 0.5


def test_find_time_exact(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="2024-09-01T06:00",
                    adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["match_kind"] == "exact"
    assert r["matches"][0]["index"] == 1


def test_find_time_first(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="first", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["index"] == 0


def test_find_time_last(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="last", adapter=NetCDFAdapter())
    r = env["result"]
    assert r["matches"][0]["index"] == 2


def test_find_time_partial(cf_4d_file):
    env = find_time(str(cf_4d_file), hint="2024-09-01",
                    adapter=NetCDFAdapter())
    r = env["result"]
    assert len(r["matches"]) >= 1
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_find.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/find.py`**

```python
# src/mcp/netcdf-reader/tools/find.py
"""⤴ format-agnostic — eligible for _core/ lift.

Hint-based search. Skills layer their own aliases.md on top; standalone
MCP users get usable disambiguation without external alias tables.
"""
from __future__ import annotations

import difflib
from typing import Any

import numpy as np

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import FormatAdapter
from src.mcp.netcdf_reader.paths.classify import classify


def _score(hint: str, candidate: str | None) -> float:
    if not candidate:
        return 0.0
    h = hint.lower(); c = candidate.lower()
    if h == c:
        return 1.0
    if h in c:
        return 0.85
    return difflib.SequenceMatcher(None, h, c).ratio()


def find_variables(path: str, hint: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        scored: list[tuple[float, dict[str, Any]]] = []
        for name, da in ds.data_vars.items():
            ln = da.attrs.get("long_name")
            sn = da.attrs.get("standard_name")
            desc = da.attrs.get("description")
            best_field = None; best_value = None; best_score = 0.0
            for field_name, field_value in (("long_name", ln),
                                            ("standard_name", sn),
                                            ("description", desc),
                                            ("name", str(name))):
                s = _score(hint, field_value)
                if s > best_score:
                    best_score = s
                    best_field = field_name
                    best_value = field_value
            scored.append((best_score, {
                "name": str(name),
                "score": round(best_score, 3),
                "matched_field": best_field,
                "matched_value": best_value,
                "long_name": ln,
                "units": da.attrs.get("units"),
            }))
        scored.sort(key=lambda x: x[0], reverse=True)
        return envelope.success({"matches": [m for _, m in scored[:10]]})
    finally:
        ds.close()


def find_time(path: str, hint: str, *, adapter: FormatAdapter) -> dict[str, Any]:
    cls = classify(path)
    ds = adapter.open(cls.paths)
    try:
        tcoord = None
        tname = None
        for n in ("time", "Time", "ocean_time"):
            if n in ds.coords or n in ds.dims:
                tcoord = ds[n].values
                tname = n
                break
        if tcoord is None:
            return envelope.error("internal_error", "no time coord", context={})

        if hint == "first":
            return envelope.success({"matches": [{
                "resolved_time": str(tcoord[0]), "index": 0,
                "match_kind": "exact", "distance": "PT0S",
            }]})
        if hint == "last":
            return envelope.success({"matches": [{
                "resolved_time": str(tcoord[-1]), "index": int(len(tcoord) - 1),
                "match_kind": "exact", "distance": "PT0S",
            }]})

        # Partial match: find all times whose ISO string starts with the hint
        iso_strs = [str(t) for t in tcoord]
        partial_matches = [
            (i, s) for i, s in enumerate(iso_strs) if s.startswith(hint)
        ]
        if partial_matches:
            return envelope.success({"matches": [
                {"resolved_time": s, "index": i,
                 "match_kind": "exact" if s == hint else "partial",
                 "distance": "PT0S"}
                for i, s in partial_matches[:10]
            ]})

        # Try exact ISO parse + nearest
        try:
            target = np.datetime64(hint)
        except (ValueError, TypeError):
            return envelope.success({"matches": []})
        diffs = np.abs(tcoord - target)
        sorted_idx = np.argsort(diffs)
        out = []
        for i in sorted_idx[:5]:
            i = int(i)
            d_seconds = int(np.abs(tcoord[i] - target) /
                            np.timedelta64(1, "s"))
            out.append({
                "resolved_time": str(tcoord[i]),
                "index": i,
                "match_kind": "exact" if d_seconds == 0 else "nearest",
                "distance": f"PT{d_seconds}S",
            })
        return envelope.success({"matches": out})
    finally:
        ds.close()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_find.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/find.py \
        tests/mcp/netcdf-reader/unit/test_find.py
git commit -m "tools/find: find_variables + find_time hint-based search"
```

---

## Phase 6: Spec annotation — `regrid_to_centers`

End of phase: U/V/W destaggering can be annotated onto a spec; renderer (cycle 2) applies the transform.

### Task 21: `regrid_to_centers()` spec annotation

**Files:**
- Create: `src/mcp/netcdf-reader/tools/transforms.py`
- Create: `tests/mcp/netcdf-reader/unit/test_transforms.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_transforms.py
from src.mcp.netcdf_reader.tools.transforms import regrid_to_centers


def test_regrid_appends_transform():
    spec = {
        "path": "/tmp/x.nc", "variable": "U",
        "selectors": {}, "resolved": {}, "slice_shape": [1, 33, 290, 201],
        "estimated_bytes": 7700000, "applied_transforms": [], "notes": [],
    }
    env = regrid_to_centers(spec)
    assert env["ok"] is True
    out = env["result"]
    transforms = out["applied_transforms"]
    assert any(t["kind"] == "regrid_to_centers" for t in transforms)


def test_regrid_idempotent():
    spec = {
        "path": "/tmp/x.nc", "variable": "U",
        "selectors": {}, "resolved": {}, "slice_shape": [1, 33, 290, 201],
        "estimated_bytes": 7700000,
        "applied_transforms": [{"kind": "regrid_to_centers"}],
        "notes": [],
    }
    env = regrid_to_centers(spec)
    out = env["result"]
    n = sum(1 for t in out["applied_transforms"] if t["kind"] == "regrid_to_centers")
    assert n == 1


def test_regrid_preserves_other_fields():
    spec = {
        "path": "/x.nc", "variable": "U",
        "selectors": {"time": "last"}, "resolved": {"time_index": 0},
        "slice_shape": [1, 1, 4, 5], "estimated_bytes": 80,
        "applied_transforms": [], "notes": ["hi"],
    }
    out = regrid_to_centers(spec)["result"]
    assert out["variable"] == "U"
    assert out["selectors"]["time"] == "last"
    assert out["notes"] == ["hi"]
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_transforms.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `tools/transforms.py`**

```python
# src/mcp/netcdf-reader/tools/transforms.py
"""⤴ format-agnostic — eligible for _core/ lift.

Spec-only annotations. The renderer (cycle 2) consumes these
annotations and applies the actual numerical transforms (e.g.,
(da[1:] + da[:-1]) / 2 along a staggered dim).
"""
from __future__ import annotations

import copy
from typing import Any

from src.mcp.netcdf_reader import envelope


def regrid_to_centers(spec: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(spec)
    transforms = out.setdefault("applied_transforms", [])
    if not any(t.get("kind") == "regrid_to_centers" for t in transforms):
        transforms.append({"kind": "regrid_to_centers"})
        out.setdefault("notes", []).append(
            "regrid_to_centers annotated; renderer applies (a[1:] + a[:-1]) / 2 along staggered dims"
        )
    return envelope.success(out)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_transforms.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/transforms.py \
        tests/mcp/netcdf-reader/unit/test_transforms.py
git commit -m "tools/transforms: regrid_to_centers spec annotation"
```

---

## Phase 7: Multi-file dataset support

End of phase: glob and directory paths open via `open_mfdataset` with combine fallback; cache key includes resolved file list.

### Task 22: Multi-file fixture builder

**Files:**
- Modify: `tests/mcp/netcdf-reader/conftest.py`

- [ ] **Step 1: Append a multi-file fixture**

```python
# Append to tests/mcp/netcdf-reader/conftest.py
@pytest.fixture
def cf_multifile_dir(tmp_path: Path) -> Path:
    """Three CF files split on time, sortable by name."""
    import numpy as np
    import xarray as xr
    out = tmp_path / "multi"; out.mkdir()
    for i, day in enumerate(["01", "02", "03"]):
        times = np.array([f"2024-09-{day}T00", f"2024-09-{day}T12"],
                         dtype="datetime64[h]")
        lat = np.linspace(-90, 90, 9)
        lon = np.linspace(0, 350, 18)
        rng = np.random.default_rng(i)
        data = rng.normal(290, 5, size=(2, 9, 18)).astype("float32")
        ds = xr.Dataset(
            {"tos": xr.DataArray(data, dims=("time", "lat", "lon"),
                                  coords={"time": times, "lat": lat, "lon": lon},
                                  attrs={"long_name": "Sea Surface Temperature",
                                         "units": "K"})},
            attrs={"Conventions": "CF-1.7"},
        )
        ds.to_netcdf(out / f"tos_2024-09-{day}.nc")
    return out
```

- [ ] **Step 2: Quick sanity test of the fixture**

```python
# Add to tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
def test_multifile_fixture(cf_multifile_dir):
    files = sorted(cf_multifile_dir.glob("*.nc"))
    assert len(files) == 3
```

- [ ] **Step 3: Run smoke test**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conftest_smoke.py -v
```

Expected: green.

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/netcdf-reader/conftest.py \
        tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
git commit -m "tests: multi-file CF fixture"
```

---

### Task 23: `paths/multi_file.py` — `open_mfdataset` with combine fallback

**Files:**
- Create: `src/mcp/netcdf-reader/paths/multi_file.py`
- Create: `tests/mcp/netcdf-reader/unit/test_multi_file.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_multi_file.py
import pytest
import xarray as xr
from src.mcp.netcdf_reader.paths.multi_file import (
    open_multi_file, MultiFileCombineError,
)


def test_open_multi_file_combines_by_coords(cf_multifile_dir):
    paths = sorted(str(p) for p in cf_multifile_dir.glob("*.nc"))
    ds = open_multi_file(paths)
    assert isinstance(ds, xr.Dataset)
    assert ds.sizes["time"] == 6  # 3 files × 2 timesteps
    ds.close()


def test_open_multi_file_falls_back_to_nested(tmp_path):
    """Files that can't combine by_coords because of attribute conflicts
    fall back to combine='nested' along the time dim."""
    import numpy as np
    out = tmp_path / "conflicting"; out.mkdir()
    for i in range(2):
        ds = xr.Dataset(
            {"v": (("time", "lat"), np.zeros((1, 3), dtype="float32"))},
            coords={"time": [np.datetime64(f"2024-09-0{i+1}")],
                    "lat": np.array([0, 1, 2], dtype="float32")},
            attrs={"history": f"created run {i}"},  # conflicting attr
        )
        ds.to_netcdf(out / f"f{i}.nc")
    files = sorted(str(p) for p in out.glob("*.nc"))
    ds_out = open_multi_file(files)
    assert ds_out.sizes["time"] == 2
    ds_out.close()


def test_open_multi_file_raises_on_unmergeable(tmp_path):
    """Files with completely incompatible structures raise."""
    import numpy as np
    out = tmp_path / "incompat"; out.mkdir()
    ds1 = xr.Dataset({"a": (("x",), np.array([1, 2, 3]))})
    ds2 = xr.Dataset({"b": (("y",), np.array([1, 2]))})
    ds1.to_netcdf(out / "1.nc")
    ds2.to_netcdf(out / "2.nc")
    with pytest.raises(MultiFileCombineError):
        open_multi_file([str(out / "1.nc"), str(out / "2.nc")])
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_multi_file.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `paths/multi_file.py`**

```python
# src/mcp/netcdf-reader/paths/multi_file.py
"""Format-specific (NetCDF): multi-file dataset opening with combine
fallback. Other formats (Zarr, GRIB) handle multi-file differently —
they keep their own paths/multi_file equivalents.
"""
from __future__ import annotations

import xarray as xr


class MultiFileCombineError(RuntimeError):
    pass


def open_multi_file(paths: list[str]) -> xr.Dataset:
    try:
        return xr.open_mfdataset(paths, combine="by_coords",
                                 parallel=False, decode_times=True,
                                 chunks="auto", compat="override")
    except Exception as first_err:
        # Fallback: nested combine on most likely concat dim
        for concat_dim in ("time", "Time", "ocean_time"):
            try:
                return xr.open_mfdataset(
                    paths, combine="nested", concat_dim=concat_dim,
                    parallel=False, decode_times=True, chunks="auto",
                )
            except Exception:
                continue
        raise MultiFileCombineError(
            f"could not combine {len(paths)} files: {first_err!s}"
        )
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_multi_file.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/multi_file.py \
        tests/mcp/netcdf-reader/unit/test_multi_file.py
git commit -m "paths/multi_file: open_mfdataset + nested-combine fallback"
```

---

### Task 24: `inspect()` against multi-file glob

**Files:**
- Modify: `tests/mcp/netcdf-reader/unit/test_inspect.py`

- [ ] **Step 1: Add a failing test for multi-file `inspect`**

```python
# Append to tests/mcp/netcdf-reader/unit/test_inspect.py

def test_inspect_multifile_glob(cf_multifile_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    glob_path = str(cf_multifile_dir / "*.nc")
    env = inspect(glob_path, adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_multi"
    assert len(r["files"]) == 3
    assert r["time"]["n"] == 6
    assert "tos" in [v["name"] for v in r["variables"]]


def test_inspect_multifile_directory(cf_multifile_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(cf_multifile_dir), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["kind"] == "local_multi"
    assert len(r["files"]) == 3
```

- [ ] **Step 2: Run — these should pass already (multi_file module is wired through `adapter.open`)**

```bash
pytest tests/mcp/netcdf-reader/unit/test_inspect.py -v -k multifile
```

Expected: 2 passed.

- [ ] **Step 3: Run all unit tests**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: all green (~80 tests).

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/netcdf-reader/unit/test_inspect.py
git commit -m "tests/inspect: multi-file glob + directory paths"
```

---

## Phase 8: WRF and ROMS conventions

End of phase: WRF and ROMS files are detected at inspect time; WRF `Times` byte-strings decoded to CF datetimes; ROMS curvilinear coords surfaced.

### Task 25: WRF + ROMS synthetic fixtures

**Files:**
- Modify: `tests/mcp/netcdf-reader/conftest.py`

- [ ] **Step 1: Append WRF fixture**

```python
# Append to tests/mcp/netcdf-reader/conftest.py
@pytest.fixture
def wrf_file(tmp_path: Path) -> Path:
    """Mimics WRF: TITLE attr, Times byte-strings, staggered dims, 2D XLAT/XLONG."""
    import numpy as np
    import xarray as xr
    n_t, n_z, n_y, n_x = 3, 4, 5, 6
    times_str = ["2024-09-01_00:00:00", "2024-09-01_06:00:00", "2024-09-01_12:00:00"]
    times = np.array([s.encode("ascii") for s in times_str]).reshape(n_t, 19)
    xlat = np.tile(np.linspace(25, 50, n_y).reshape(n_y, 1), (1, n_x)).astype("float32")
    xlong = np.tile(np.linspace(-130, -90, n_x).reshape(1, n_x), (n_y, 1)).astype("float32")
    rng = np.random.default_rng(0)
    t2 = rng.normal(290, 5, size=(n_t, n_y, n_x)).astype("float32")
    u_stag = rng.normal(5, 2, size=(n_t, n_z, n_y, n_x + 1)).astype("float32")
    ds = xr.Dataset(
        {
            "Times": (("Time", "DateStrLen"), times),
            "T2": (("Time", "south_north", "west_east"), t2,
                   {"description": "TEMP at 2 M", "units": "K"}),
            "U": (("Time", "bottom_top", "south_north", "west_east_stag"), u_stag,
                  {"description": "x-wind component", "units": "m s-1"}),
            "XLAT": (("south_north", "west_east"), xlat, {"units": "degree_north"}),
            "XLONG": (("south_north", "west_east"), xlong, {"units": "degree_east"}),
        },
        attrs={"TITLE": "OUTPUT FROM WRF V4.5", "GRIDTYPE": "C", "MMINLU": "USGS"},
    )
    p = tmp_path / "wrfout.nc"
    ds.to_netcdf(p)
    return p


@pytest.fixture
def roms_file(tmp_path: Path) -> Path:
    """Mimics ROMS: s_rho/Cs_r vertical, lat_rho/lon_rho 2D, ocean_time."""
    import numpy as np
    import xarray as xr
    n_t, n_s, n_y, n_x = 2, 3, 4, 5
    ocean_time = np.array(
        ["2024-09-01", "2024-09-02"], dtype="datetime64[D]"
    )
    s_rho = np.linspace(-1.0, 0.0, n_s)
    cs_r = -np.linspace(0.5, 0.0, n_s)
    lat_rho = np.tile(np.linspace(30, 35, n_y).reshape(n_y, 1), (1, n_x)).astype("float32")
    lon_rho = np.tile(np.linspace(-75, -70, n_x).reshape(1, n_x), (n_y, 1)).astype("float32")
    rng = np.random.default_rng(0)
    temp = rng.normal(15, 3, size=(n_t, n_s, n_y, n_x)).astype("float32")
    ds = xr.Dataset(
        {
            "temp": (("ocean_time", "s_rho", "eta_rho", "xi_rho"), temp,
                     {"long_name": "potential temperature", "units": "C"}),
            "lat_rho": (("eta_rho", "xi_rho"), lat_rho, {"units": "degree_north"}),
            "lon_rho": (("eta_rho", "xi_rho"), lon_rho, {"units": "degree_east"}),
            "s_rho": (("s_rho",), s_rho, {"long_name": "S-coord at rho",
                                          "standard_name": "ocean_s_coordinate_g2"}),
            "Cs_r": (("s_rho",), cs_r, {"long_name": "S-coord stretching at rho"}),
        },
        coords={"ocean_time": ocean_time},
        attrs={"type": "ROMS/TOMS history file"},
    )
    p = tmp_path / "roms.nc"
    ds.to_netcdf(p)
    return p
```

- [ ] **Step 2: Smoke test**

```python
# Append to tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
def test_wrf_fixture_opens(wrf_file):
    import xarray as xr
    ds = xr.open_dataset(wrf_file)
    assert "T2" in ds.data_vars
    assert "west_east_stag" in ds.dims
    ds.close()


def test_roms_fixture_opens(roms_file):
    import xarray as xr
    ds = xr.open_dataset(roms_file)
    assert "s_rho" in ds.dims
    assert ds["lat_rho"].ndim == 2
    ds.close()
```

```bash
pytest tests/mcp/netcdf-reader/unit/test_conftest_smoke.py -v
```

Expected: green.

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/netcdf-reader/conftest.py \
        tests/mcp/netcdf-reader/unit/test_conftest_smoke.py
git commit -m "tests: WRF + ROMS synthetic fixtures"
```

---

### Task 26: WRF detection signals

**Files:**
- Create: `src/mcp/netcdf-reader/conventions/wrf.py`
- Create: `tests/mcp/netcdf-reader/unit/test_conventions_wrf.py`

- [ ] **Step 1: Write failing detection tests**

```python
# tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
import xarray as xr
from src.mcp.netcdf_reader.conventions.wrf import detect


def test_wrf_detected_from_title(wrf_file):
    ds = xr.open_dataset(wrf_file)
    result = detect(ds, ds.attrs)
    assert result["primary"] == "WRF"
    assert result["confidence"] == "high"
    assert any("TITLE" in e for e in result["evidence"])
    ds.close()


def test_non_wrf_returns_none(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    result = detect(ds, ds.attrs)
    assert result is None
    ds.close()


def test_wrf_detected_from_staggered_dims(tmp_path):
    """File with WRF-style staggered dims but no TITLE attr."""
    import numpy as np
    ds = xr.Dataset(
        {"x": (("south_north", "west_east_stag"),
               np.zeros((3, 4), dtype="float32"))},
    )
    p = tmp_path / "noattr.nc"; ds.to_netcdf(p)
    ds2 = xr.open_dataset(p)
    result = detect(ds2, ds2.attrs)
    assert result is not None
    assert result["primary"] == "WRF"
    assert result["confidence"] in ("medium", "low")
    ds2.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v
```

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `conventions/wrf.py` — detection only**

```python
# src/mcp/netcdf-reader/conventions/wrf.py
"""Format-specific (NetCDF): WRF-aware detection and helpers.
WRF is not CF-compliant; we surface it at inspect time so skills
and consumers can apply WRF-aware logic.
"""
from __future__ import annotations

from typing import Any

import xarray as xr


_STAGGERED_DIMS = {"west_east_stag", "south_north_stag", "bottom_top_stag"}


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []

    title = attrs.get("TITLE", "")
    if isinstance(title, str) and "WRF" in title.upper():
        evidence.append(f"TITLE attr matches {title!r}")
    if "MMINLU" in attrs:
        evidence.append(f"MMINLU attr present (value={attrs['MMINLU']!r})")

    staggered = _STAGGERED_DIMS & set(map(str, ds.dims))
    if staggered:
        evidence.append(f"WRF-style staggered dims present: {sorted(staggered)}")

    if "Times" in ds.data_vars and ds["Times"].dtype.kind in ("S", "O"):
        evidence.append("Times byte-string variable present")

    if not evidence:
        return None

    if any("TITLE" in e for e in evidence):
        confidence = "high"
    elif len(evidence) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "primary": "WRF",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/wrf.py \
        tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
git commit -m "conventions/wrf: detection from TITLE/staggered/Times"
```

---

### Task 27: WRF Times decoding

**Files:**
- Modify: `src/mcp/netcdf-reader/conventions/wrf.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_conventions_wrf.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
import numpy as np
from src.mcp.netcdf_reader.conventions.wrf import decode_times


def test_decode_times_returns_datetime64(wrf_file):
    ds = xr.open_dataset(wrf_file)
    times = decode_times(ds)
    assert times is not None
    assert times.dtype.kind == "M"
    assert len(times) == 3
    assert str(times[0]).startswith("2024-09-01T00")
    assert str(times[2]).startswith("2024-09-01T12")
    ds.close()


def test_decode_times_returns_none_when_absent(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert decode_times(ds) is None
    ds.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v -k decode_times
```

Expected: ImportError.

- [ ] **Step 3: Append `decode_times` to `wrf.py`**

```python
# Append to src/mcp/netcdf-reader/conventions/wrf.py
import numpy as np


def decode_times(ds: xr.Dataset) -> np.ndarray | None:
    """Decode WRF Times byte-string array to CF datetime64."""
    if "Times" not in ds.data_vars:
        return None
    raw = ds["Times"].values
    # raw is shape (n_time, str_len) of bytes. Stitch bytes per row.
    if raw.ndim == 2:
        rows = [b"".join(row).decode("ascii", errors="replace") for row in raw]
    else:
        rows = [s.decode("ascii", errors="replace") if isinstance(s, bytes) else str(s)
                for s in raw]
    # WRF format: "2024-09-01_06:00:00" → ISO "2024-09-01T06:00:00"
    iso = [s.replace("_", "T").rstrip("\x00 ") for s in rows]
    return np.array(iso, dtype="datetime64[s]")
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/wrf.py \
        tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
git commit -m "conventions/wrf: decode Times byte-strings to datetime64"
```

---

### Task 28: WRF — staggered grid recognition + curvilinear spatial

**Files:**
- Modify: `src/mcp/netcdf-reader/conventions/wrf.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_conventions_wrf.py`

- [ ] **Step 1: Append failing tests**

```python
# Append to tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
from src.mcp.netcdf_reader.conventions.wrf import (
    annotate_staggered_variables, extract_spatial_wrf,
)


def test_annotate_staggered_marks_U_as_staggered(wrf_file):
    ds = xr.open_dataset(wrf_file)
    annotated = annotate_staggered_variables(ds)
    by_name = {v["name"]: v for v in annotated}
    assert by_name["U"]["is_staggered"] is True
    assert by_name["U"]["grid_kind"] == "U"
    assert by_name["T2"]["is_staggered"] is False
    assert by_name["T2"]["grid_kind"] == "scalar"
    ds.close()


def test_extract_spatial_wrf_curvilinear(wrf_file):
    ds = xr.open_dataset(wrf_file)
    s = extract_spatial_wrf(ds)
    assert s["coord_kind"] == "curvilinear"
    assert s["lat_name"] == "XLAT"
    assert s["lon_name"] == "XLONG"
    assert s["lon_convention"] == "-180..180"
    ds.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v -k staggered_marks_U or curvilinear
```

Expected: ImportError.

- [ ] **Step 3: Append helpers to `wrf.py`**

```python
# Append to src/mcp/netcdf-reader/conventions/wrf.py
def _grid_kind_from_dims(dims: tuple[str, ...]) -> str:
    if "west_east_stag" in dims:
        return "U"
    if "south_north_stag" in dims:
        return "V"
    if "bottom_top_stag" in dims:
        return "W"
    return "scalar"


def annotate_staggered_variables(ds: xr.Dataset) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for name, da in ds.data_vars.items():
        gk = _grid_kind_from_dims(tuple(str(d) for d in da.dims))
        out.append({
            "name": str(name),
            "long_name": da.attrs.get("long_name") or da.attrs.get("description"),
            "standard_name": da.attrs.get("standard_name"),
            "units": da.attrs.get("units"),
            "dims": [str(d) for d in da.dims],
            "shape": list(da.shape),
            "dtype": str(da.dtype),
            "grid_kind": gk,
            "is_staggered": gk != "scalar",
        })
    return out


def extract_spatial_wrf(ds: xr.Dataset) -> dict[str, Any] | None:
    if "XLAT" not in ds.coords and "XLAT" not in ds.data_vars:
        return None
    lat = ds["XLAT"]
    lon = ds["XLONG"]
    # WRF XLAT/XLONG can be (Time, south_north, west_east); take first time
    if lat.ndim == 3:
        lat = lat.isel({lat.dims[0]: 0})
        lon = lon.isel({lon.dims[0]: 0})
    coord_kind = "curvilinear" if lat.ndim == 2 else "rectilinear"
    lon_min = float(lon.min())
    lon_max = float(lon.max())
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"
    return {
        "coord_kind": coord_kind,
        "lat_name": "XLAT",
        "lon_name": "XLONG",
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": lon_convention,
    }
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_wrf.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/wrf.py \
        tests/mcp/netcdf-reader/unit/test_conventions_wrf.py
git commit -m "conventions/wrf: staggered annotation + curvilinear spatial"
```

---

### Task 29: ROMS detection + curvilinear extraction

**Files:**
- Create: `src/mcp/netcdf-reader/conventions/roms.py`
- Create: `tests/mcp/netcdf-reader/unit/test_conventions_roms.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_conventions_roms.py
import xarray as xr
from src.mcp.netcdf_reader.conventions.roms import (
    detect, extract_spatial_roms, extract_vertical_roms,
)


def test_roms_detected_from_s_rho(roms_file):
    ds = xr.open_dataset(roms_file)
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "ROMS"
    assert any("s_rho" in e or "Cs_r" in e for e in r["evidence"])
    ds.close()


def test_non_roms_returns_none(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    assert detect(ds, ds.attrs) is None
    ds.close()


def test_extract_spatial_roms_curvilinear(roms_file):
    ds = xr.open_dataset(roms_file)
    s = extract_spatial_roms(ds)
    assert s["coord_kind"] == "curvilinear"
    assert s["lat_name"] == "lat_rho"
    assert s["lon_name"] == "lon_rho"
    ds.close()


def test_extract_vertical_roms_sigma(roms_file):
    ds = xr.open_dataset(roms_file)
    v = extract_vertical_roms(ds)
    assert v["name"] == "s_rho"
    assert v["kind"] == "sigma"
    assert v["n"] == 3
    ds.close()
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_roms.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement `conventions/roms.py`**

```python
# src/mcp/netcdf-reader/conventions/roms.py
"""Format-specific (NetCDF): ROMS-aware detection and helpers."""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []
    if any(d in ds.dims for d in ("s_rho", "s_w")):
        evidence.append("ROMS sigma dim present (s_rho/s_w)")
    if "Cs_r" in ds.data_vars or "Cs_w" in ds.data_vars:
        evidence.append("Cs_r/Cs_w stretching variable present")
    if any(name in ds.data_vars or name in ds.coords
           for name in ("lat_rho", "lon_rho", "lat_u", "lon_u")):
        evidence.append("ROMS lat/lon_rho coords present")
    title = attrs.get("type", "")
    if isinstance(title, str) and "ROMS" in title.upper():
        evidence.append(f"type attr = {title!r}")

    if not evidence:
        return None
    confidence = "high" if len(evidence) >= 2 else "medium"
    return {
        "primary": "ROMS",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def extract_spatial_roms(ds: xr.Dataset) -> dict[str, Any] | None:
    if "lat_rho" not in ds.data_vars and "lat_rho" not in ds.coords:
        return None
    lat = ds["lat_rho"]; lon = ds["lon_rho"]
    coord_kind = "curvilinear" if lat.ndim == 2 else "rectilinear"
    lon_min = float(lon.min()); lon_max = float(lon.max())
    if lon_min >= 0 and lon_max > 180:
        conv = "0..360"
    elif lon_min < 0:
        conv = "-180..180"
    else:
        conv = "mixed"
    return {
        "coord_kind": coord_kind,
        "lat_name": "lat_rho",
        "lon_name": "lon_rho",
        "lat_range": [float(lat.min()), float(lat.max())],
        "lon_range": [lon_min, lon_max],
        "lon_convention": conv,
    }


def extract_vertical_roms(ds: xr.Dataset) -> dict[str, Any] | None:
    name = "s_rho" if "s_rho" in ds.dims else ("s_w" if "s_w" in ds.dims else None)
    if name is None:
        return None
    n = int(ds.sizes[name])
    coord = ds[name] if name in ds.coords else None
    monotonic = "unknown"
    if coord is not None and n > 1:
        diffs = np.diff(coord.values)
        if np.all(diffs > 0):
            monotonic = "increasing"
        elif np.all(diffs < 0):
            monotonic = "decreasing"
    return {
        "name": name,
        "kind": "sigma",
        "units": coord.attrs.get("units") if coord is not None else None,
        "n": n,
        "monotonic": monotonic,
    }
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_conventions_roms.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/conventions/roms.py \
        tests/mcp/netcdf-reader/unit/test_conventions_roms.py
git commit -m "conventions/roms: detection + curvilinear/sigma extraction"
```

---

### Task 30: Wire WRF/ROMS into `adapter.detect_conventions` and `inspect()`

**Files:**
- Modify: `src/mcp/netcdf-reader/adapter.py`
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_inspect.py`

- [ ] **Step 1: Append failing inspect tests for WRF and ROMS**

```python
# Append to tests/mcp/netcdf-reader/unit/test_inspect.py
def test_inspect_wrf_detected(wrf_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(wrf_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["convention"]["primary"] == "WRF"
    assert r["spatial"]["coord_kind"] == "curvilinear"
    assert r["spatial"]["lat_name"] == "XLAT"
    var_by_name = {v["name"]: v for v in r["variables"]}
    assert var_by_name["U"]["is_staggered"] is True
    assert var_by_name["U"]["grid_kind"] == "U"
    assert var_by_name["T2"]["is_staggered"] is False


def test_inspect_roms_detected(roms_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(roms_file), adapter=NetCDFAdapter())
    assert env["ok"] is True
    r = env["result"]
    assert r["convention"]["primary"] == "ROMS"
    assert r["vertical"]["kind"] == "sigma"
    assert r["spatial"]["coord_kind"] == "curvilinear"
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_inspect.py -v -k "wrf_detected or roms_detected"
```

Expected: convention says CF or unknown, not WRF/ROMS.

- [ ] **Step 3: Update `adapter.detect_conventions` to delegate to WRF / ROMS first**

Replace `NetCDFAdapter.detect_conventions` with:

```python
    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
        from src.mcp.netcdf_reader.conventions import cf as _cf
        from src.mcp.netcdf_reader.conventions import roms as _roms
        from src.mcp.netcdf_reader.conventions import wrf as _wrf
        # WRF and ROMS take precedence — they're more specific
        for det in (_wrf.detect(ds, attrs), _roms.detect(ds, attrs)):
            if det is not None:
                return det
        return _cf.detect(ds, attrs)
```

- [ ] **Step 4: Update `tools/inspect.py` to dispatch convention-specific extraction**

Replace the `try` block in `inspect()` so that variables/spatial/vertical use convention-specific helpers when applicable:

```python
    try:
        attrs = dict(ds.attrs)
        convention = adapter.detect_conventions(ds, attrs)
        primary = convention.get("primary")

        if primary == "WRF":
            from src.mcp.netcdf_reader.conventions import wrf as _wrf
            variables = _wrf.annotate_staggered_variables(ds)
            spatial = _wrf.extract_spatial_wrf(ds)
            vertical = _cf.extract_vertical(ds)  # falls back; eta detected by name
            # WRF time decoding
            decoded = _wrf.decode_times(ds)
            if decoded is not None:
                t = {
                    "name": "Time",
                    "calendar": "standard",
                    "range": [str(decoded[0]), str(decoded[-1])],
                    "step": None,
                    "n": len(decoded),
                    "monotonic": "increasing",
                }
            else:
                t = _cf.extract_time(ds)
        elif primary == "ROMS":
            from src.mcp.netcdf_reader.conventions import roms as _roms
            variables = _cf.extract_variables(ds)
            spatial = _roms.extract_spatial_roms(ds)
            vertical = _roms.extract_vertical_roms(ds)
            t = _cf.extract_time(ds)
        else:
            variables = _cf.extract_variables(ds)
            spatial = _cf.extract_spatial(ds)
            vertical = _cf.extract_vertical(ds)
            t = _cf.extract_time(ds)

        result = {
            "path": cls.raw,
            "kind": cls.kind,
            "files": cls.paths,
            "convention": convention,
            "variables": variables,
            "time": t,
            "spatial": spatial,
            "vertical": vertical,
            "dims": {str(k): int(v) for k, v in ds.sizes.items()},
            "attrs": {k: _safe(v) for k, v in attrs.items()},
        }
    finally:
        ds.close()
```

- [ ] **Step 5: Verify all inspect tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_inspect.py -v
```

Expected: all green.

- [ ] **Step 6: Run all unit tests**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: ~95 tests, all green.

- [ ] **Step 7: Commit**

```bash
git add src/mcp/netcdf-reader/adapter.py \
        src/mcp/netcdf-reader/tools/inspect.py \
        tests/mcp/netcdf-reader/unit/test_inspect.py
git commit -m "adapter+inspect: dispatch WRF/ROMS before CF in detection"
```

---

## Phase 9: Remote URL support

End of phase: HTTP/HTTPS/S3 paths pass through to xarray; appropriate error envelopes when deps missing.

### Task 31: Remote URL passthrough in adapter + inspect

**Files:**
- Modify: `src/mcp/netcdf-reader/adapter.py`
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Create: `tests/mcp/netcdf-reader/unit/test_remote.py`

- [ ] **Step 1: Write failing tests (mocked)**

```python
# tests/mcp/netcdf-reader/unit/test_remote.py
import pytest
from unittest.mock import patch, MagicMock
from src.mcp.netcdf_reader.adapter import NetCDFAdapter


def test_adapter_passes_http_url_to_open_dataset(monkeypatch):
    captured = {}
    def fake_open(path, **kwargs):
        captured["path"] = path
        captured["kwargs"] = kwargs
        return MagicMock(data_vars={}, coords={}, dims={}, sizes={}, attrs={})
    monkeypatch.setattr("xarray.open_dataset", fake_open)
    a = NetCDFAdapter()
    ds = a.open(["https://example.org/data.nc"])
    assert captured["path"] == "https://example.org/data.nc"


def test_classify_recognises_s3():
    from src.mcp.netcdf_reader.paths.classify import classify, PathKind
    k = classify("s3://bucket/path/file.nc")
    assert k.kind == PathKind.REMOTE_URL
    assert k.scheme == "s3"


def test_inspect_handles_open_failure_for_remote(tmp_path, monkeypatch):
    """If xarray fails on a remote URL (e.g., connection refused), we
    return a clear error envelope rather than a stack trace."""
    monkeypatch.chdir(tmp_path)
    from src.mcp.netcdf_reader.tools.inspect import inspect

    def fake_open_dataset(path, **kwargs):
        raise OSError("Network unreachable")
    monkeypatch.setattr("xarray.open_dataset", fake_open_dataset)
    env = inspect("https://example.org/x.nc", adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] in (
        "remote_file_not_found", "internal_error", "ssh_timeout",
    )
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_remote.py -v
```

Expected: the error-envelope test fails (currently inspect lets the OSError propagate).

- [ ] **Step 3: Wrap the open call in `inspect()` with structured error handling**

In `tools/inspect.py`, replace the `try: ds = adapter.open(cls.paths)` block:

```python
    try:
        ds = adapter.open(cls.paths)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"path": path})
    except OSError as e:
        # network or SSH-style errors
        msg = str(e)
        code = (envelope.ErrorCode.REMOTE_FILE_NOT_FOUND
                if cls.kind in ("remote_url", "ssh_remote")
                else envelope.ErrorCode.FILE_NOT_FOUND)
        return envelope.error(code, msg, context={"path": path})
    except Exception as e:
        return envelope.error(envelope.ErrorCode.INTERNAL_ERROR,
                              repr(e), context={"path": path})
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_remote.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/inspect.py \
        tests/mcp/netcdf-reader/unit/test_remote.py
git commit -m "remote: structured error envelope on remote/network failure"
```

---

## Phase 10: SSH transport

End of phase: `ssh://` paths work end-to-end with the silent auth chain, structured credential prompts, session-pooled SFTP connections, multi-step auth, and jump hosts. All tests via `paramiko` mocks (real-SSH integration is opt-in, in Phase 12).

### Task 32: SSH config dataclass + parser shim

**Files:**
- Create: `src/mcp/netcdf-reader/paths/ssh.py` (initial skeleton)
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_config.py`

- [ ] **Step 1: Write failing tests for SSH config parsing**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_config.py
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, parse_ssh_config_for_host,
)


def test_ssh_config_dataclass_defaults():
    cfg = SSHConfig(host="h")
    assert cfg.host == "h"
    assert cfg.port == 22
    assert cfg.user is None
    assert cfg.identity_file is None
    assert cfg.jump is None


def test_parse_ssh_config_simple_alias(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text(
        "Host hpc\n"
        "  HostName hpc.example.org\n"
        "  User youngsung\n"
        "  IdentityFile ~/.ssh/id_rsa\n"
        "  Port 2222\n"
    )
    cfg = parse_ssh_config_for_host("hpc", config_path=str(cfile))
    assert cfg.host == "hpc.example.org"
    assert cfg.user == "youngsung"
    assert cfg.port == 2222
    assert cfg.identity_file == "~/.ssh/id_rsa"


def test_parse_ssh_config_no_match_returns_passthrough(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text("Host other\n  HostName other.example.org\n")
    cfg = parse_ssh_config_for_host("missing", config_path=str(cfile))
    assert cfg.host == "missing"
    assert cfg.user is None


def test_parse_ssh_config_with_proxyjump(tmp_path):
    cfile = tmp_path / "ssh_config"
    cfile.write_text(
        "Host inner\n"
        "  HostName internal.hpc.org\n"
        "  User u\n"
        "  ProxyJump bastion\n"
        "Host bastion\n"
        "  HostName bastion.example.org\n"
        "  User u\n"
    )
    cfg = parse_ssh_config_for_host("inner", config_path=str(cfile))
    assert cfg.host == "internal.hpc.org"
    assert cfg.jump is not None
    assert cfg.jump.host == "bastion.example.org"
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_config.py -v
```

Expected: ModuleNotFoundError.

- [ ] **Step 3: Implement initial `paths/ssh.py` — config dataclass + parser**

```python
# src/mcp/netcdf-reader/paths/ssh.py
"""⤴ format-agnostic — eligible for _core/ lift.

SSH transport. paramiko opens an SFTP client; xarray reads the file
through it via the h5netcdf engine. Connection pool is session-scoped.
Credentials live only in process memory.

This module is built up across Tasks 32–39. Read the spec §7.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import paramiko


@dataclass
class SSHConfig:
    host: str
    port: int = 22
    user: str | None = None
    identity_file: str | None = None
    passphrase: str | None = None  # for encrypted keys
    password: str | None = None
    jump: "SSHConfig | None" = None
    session_id: str | None = None


def parse_ssh_config_for_host(
    alias: str, *, config_path: str | None = None
) -> SSHConfig:
    """Use paramiko's SSHConfig parser to resolve a host alias from the
    user's ~/.ssh/config (or the given config_path). Returns a passthrough
    SSHConfig if no alias matches."""
    if config_path is None:
        config_path = str(Path.home() / ".ssh" / "config")
    if not Path(config_path).exists():
        return SSHConfig(host=alias)

    sc = paramiko.SSHConfig()
    with open(config_path) as fh:
        sc.parse(fh)

    look = sc.lookup(alias)
    host = look.get("hostname", alias)
    port = int(look.get("port", 22))
    user = look.get("user")
    identity = (look.get("identityfile") or [None])[0]

    jump = None
    pj = look.get("proxyjump")
    if pj:
        # ProxyJump may be "bastion" or "user@bastion:port"
        # Recurse to resolve the jump host's own config
        if "@" in pj:
            j_user, j_host = pj.split("@", 1)
        else:
            j_user, j_host = None, pj
        if ":" in j_host:
            j_host, j_port = j_host.split(":", 1)
            j_port = int(j_port)
        else:
            j_port = 22
        jump_resolved = parse_ssh_config_for_host(j_host, config_path=config_path)
        if j_user:
            jump_resolved.user = j_user
        if j_port != 22:
            jump_resolved.port = j_port
        jump = jump_resolved

    return SSHConfig(
        host=host, port=port, user=user, identity_file=identity, jump=jump,
    )
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_config.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/ssh.py \
        tests/mcp/netcdf-reader/unit/test_ssh_config.py
git commit -m "paths/ssh: SSHConfig dataclass + ~/.ssh/config parser"
```

---

### Task 33: Silent auth chain (config → agent → default identities)

**Files:**
- Modify: `src/mcp/netcdf-reader/paths/ssh.py`
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_silent_auth.py`

- [ ] **Step 1: Write failing tests with paramiko mocks**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_silent_auth.py
from unittest.mock import MagicMock, patch
import pytest
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, AuthAttempt, silent_auth_chain, SSHAuthNeeded,
)


def test_silent_auth_succeeds_with_agent_keys():
    cfg = SSHConfig(host="h", user="u")
    fake_client = MagicMock()
    with patch("paramiko.SSHClient") as MockClient, \
         patch.dict("os.environ", {"SSH_AUTH_SOCK": "/tmp/agent.sock"}):
        MockClient.return_value.connect.return_value = None
        MockClient.return_value = fake_client
        # First connect call (agent) succeeds
        client, attempts = silent_auth_chain(cfg)
        assert client is not None
        assert any(a.method == "ssh_agent" and a.result == "success"
                   for a in attempts)


def test_silent_auth_falls_through_and_raises_when_all_fail():
    cfg = SSHConfig(host="h", user="u")
    with patch("paramiko.SSHClient") as MockClient, \
         patch.dict("os.environ", {}, clear=True):
        # Every connect call raises AuthenticationException
        MockClient.return_value.connect.side_effect = (
            paramiko_AuthenticationException("nope")
        )
        with pytest.raises(SSHAuthNeeded) as excinfo:
            silent_auth_chain(cfg)
        attempts = excinfo.value.attempts
        # ssh-agent skipped (no SSH_AUTH_SOCK), default identities tried
        assert any(a.method == "default_identity_files" for a in attempts)


def paramiko_AuthenticationException(msg):
    import paramiko
    return paramiko.AuthenticationException(msg)
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_silent_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Append silent-auth-chain code to `ssh.py`**

```python
# Append to src/mcp/netcdf-reader/paths/ssh.py

@dataclass
class AuthAttempt:
    method: str
    result: str  # "success" | "no_keys" | "rejected" | "skipped"
    detail: str = ""


class SSHAuthNeeded(Exception):
    """Raised when silent auth chain exhausts all options. The agent
    layer converts this into an `ssh_auth_needed` envelope."""
    def __init__(self, cfg: SSHConfig, attempts: list[AuthAttempt],
                 may_need_jump_host: bool = False):
        self.cfg = cfg
        self.attempts = attempts
        self.may_need_jump_host = may_need_jump_host
        super().__init__(f"SSH auth needed for {cfg.user}@{cfg.host}")


def _default_identity_files() -> list[str]:
    home = Path.home()
    return [str(home / ".ssh" / n)
            for n in ("id_ed25519", "id_rsa", "id_ecdsa")
            if (home / ".ssh" / n).exists()]


def silent_auth_chain(
    cfg: SSHConfig,
) -> tuple[paramiko.SSHClient, list[AuthAttempt]]:
    """Try each silent auth method in order. Return the connected
    client + the trace of attempts. Raise SSHAuthNeeded on total failure.
    """
    attempts: list[AuthAttempt] = []
    user = cfg.user or os.environ.get("USER") or "root"

    # 1. ssh-agent (only if SSH_AUTH_SOCK is set)
    if os.environ.get("SSH_AUTH_SOCK"):
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=cfg.host, port=cfg.port, username=user,
                allow_agent=True, look_for_keys=False,
                timeout=10,
            )
            attempts.append(AuthAttempt("ssh_agent", "success"))
            return client, attempts
        except paramiko.AuthenticationException:
            attempts.append(AuthAttempt("ssh_agent", "rejected"))
        except (OSError, paramiko.SSHException) as e:
            attempts.append(AuthAttempt("ssh_agent", "rejected", str(e)))
    else:
        attempts.append(AuthAttempt("ssh_agent", "skipped",
                                    "SSH_AUTH_SOCK not set"))

    # 2. Default identity files
    if cfg.identity_file:
        candidates = [cfg.identity_file]
    else:
        candidates = _default_identity_files()
    if not candidates:
        attempts.append(AuthAttempt("default_identity_files", "no_keys"))
    for ident in candidates:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=cfg.host, port=cfg.port, username=user,
                key_filename=ident, allow_agent=False, look_for_keys=False,
                timeout=10,
            )
            attempts.append(AuthAttempt("default_identity_files", "success",
                                        ident))
            return client, attempts
        except paramiko.AuthenticationException:
            attempts.append(AuthAttempt("default_identity_files", "rejected",
                                        ident))
        except paramiko.PasswordRequiredException:
            attempts.append(AuthAttempt("default_identity_files",
                                        "needs_passphrase", ident))
        except (OSError, paramiko.SSHException) as e:
            attempts.append(AuthAttempt("default_identity_files",
                                        "rejected", f"{ident}: {e}"))

    raise SSHAuthNeeded(cfg=cfg, attempts=attempts)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_silent_auth.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/ssh.py \
        tests/mcp/netcdf-reader/unit/test_ssh_silent_auth.py
git commit -m "paths/ssh: silent auth chain + SSHAuthNeeded"
```

---

### Task 34: Explicit auth (password + identity_file + passphrase)

**Files:**
- Modify: `src/mcp/netcdf-reader/paths/ssh.py`
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_explicit_auth.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_explicit_auth.py
from unittest.mock import MagicMock, patch
import pytest
import paramiko
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, connect_explicit, SSHAuthFailed,
)


def test_connect_with_password():
    cfg = SSHConfig(host="h", user="u", password="secret")
    fake = MagicMock()
    with patch("paramiko.SSHClient", return_value=fake):
        client = connect_explicit(cfg)
        fake.connect.assert_called_once()
        kwargs = fake.connect.call_args.kwargs
        assert kwargs["password"] == "secret"
        assert kwargs["username"] == "u"


def test_connect_with_identity_and_passphrase():
    cfg = SSHConfig(host="h", user="u",
                    identity_file="/k/key", passphrase="ppp")
    fake = MagicMock()
    with patch("paramiko.SSHClient", return_value=fake):
        connect_explicit(cfg)
        kwargs = fake.connect.call_args.kwargs
        assert kwargs["key_filename"] == "/k/key"
        assert kwargs["passphrase"] == "ppp"


def test_connect_failed_raises_ssh_auth_failed():
    cfg = SSHConfig(host="h", user="u", password="wrong")
    fake = MagicMock()
    fake.connect.side_effect = paramiko.AuthenticationException("denied")
    with patch("paramiko.SSHClient", return_value=fake):
        with pytest.raises(SSHAuthFailed):
            connect_explicit(cfg)


def test_password_not_logged(caplog):
    cfg = SSHConfig(host="h", user="u", password="hunter2")
    fake = MagicMock()
    fake.connect.side_effect = paramiko.AuthenticationException("denied")
    with patch("paramiko.SSHClient", return_value=fake):
        try:
            connect_explicit(cfg)
        except SSHAuthFailed:
            pass
    assert "hunter2" not in caplog.text
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_explicit_auth.py -v
```

Expected: ImportError.

- [ ] **Step 3: Append explicit-auth code to `ssh.py`**

```python
# Append to src/mcp/netcdf-reader/paths/ssh.py
class SSHAuthFailed(Exception):
    pass


def connect_explicit(cfg: SSHConfig) -> paramiko.SSHClient:
    """Connect using credentials present in `cfg`. Raises SSHAuthFailed
    on rejection. Never logs sensitive fields."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    user = cfg.user or os.environ.get("USER") or "root"
    try:
        kwargs: dict[str, Any] = dict(
            hostname=cfg.host, port=cfg.port, username=user,
            allow_agent=False, look_for_keys=False, timeout=10,
        )
        if cfg.password is not None:
            kwargs["password"] = cfg.password
        if cfg.identity_file is not None:
            kwargs["key_filename"] = cfg.identity_file
            if cfg.passphrase is not None:
                kwargs["passphrase"] = cfg.passphrase
        client.connect(**kwargs)
        return client
    except paramiko.AuthenticationException as e:
        raise SSHAuthFailed(f"auth rejected for {user}@{cfg.host}") from None
    except (OSError, paramiko.SSHException) as e:
        # Don't include cfg in the exception message — could leak
        raise SSHAuthFailed(f"connection error: {type(e).__name__}") from None
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_explicit_auth.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/ssh.py \
        tests/mcp/netcdf-reader/unit/test_ssh_explicit_auth.py
git commit -m "paths/ssh: explicit auth (password / key+passphrase)"
```

---

### Task 35: SSH connection pool (session-scoped)

**Files:**
- Modify: `src/mcp/netcdf-reader/paths/ssh.py`
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_pool.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_pool.py
from unittest.mock import MagicMock, patch
from src.mcp.netcdf_reader.paths.ssh import (
    SSHConfig, ConnectionPool,
)


def test_pool_returns_same_client_for_same_host():
    pool = ConnectionPool()
    cfg = SSHConfig(host="h", port=22, user="u")
    fake = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake) as connect:
        c1 = pool.get_or_open(cfg)
        c2 = pool.get_or_open(cfg)
        assert c1 is c2
        connect.assert_called_once()


def test_pool_separates_different_user_or_host():
    pool = ConnectionPool()
    fake_a, fake_b = MagicMock(), MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               side_effect=[fake_a, fake_b]):
        c1 = pool.get_or_open(SSHConfig(host="h1", user="u"))
        c2 = pool.get_or_open(SSHConfig(host="h2", user="u"))
        assert c1 is not c2


def test_pool_close_all_calls_each_close():
    pool = ConnectionPool()
    fakes = [MagicMock(), MagicMock()]
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               side_effect=fakes):
        pool.get_or_open(SSHConfig(host="h1", user="u"))
        pool.get_or_open(SSHConfig(host="h2", user="u"))
    pool.close_all()
    for f in fakes:
        f.close.assert_called_once()
    assert len(pool._pool) == 0


def test_pool_zeros_credentials_on_close():
    pool = ConnectionPool()
    cfg = SSHConfig(host="h", user="u", password="hunter2")
    fake = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake):
        pool.get_or_open(cfg)
        pool.close_all()
    # The stored cfg's password field should be cleared
    assert cfg.password is None or cfg.password == ""
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_pool.py -v
```

Expected: ImportError.

- [ ] **Step 3: Append pool to `ssh.py`**

```python
# Append to src/mcp/netcdf-reader/paths/ssh.py
class ConnectionPool:
    """Session-scoped pool keyed by (user, host, port). Credentials
    live only in the in-memory cfg objects; cleared on close_all()."""
    def __init__(self) -> None:
        self._pool: dict[tuple[str, str, int], tuple[paramiko.SSHClient, SSHConfig]] = {}

    def _key(self, cfg: SSHConfig) -> tuple[str, str, int]:
        return (cfg.user or "", cfg.host, cfg.port)

    def get_or_open(self, cfg: SSHConfig) -> paramiko.SSHClient:
        k = self._key(cfg)
        if k in self._pool:
            return self._pool[k][0]
        client = connect_explicit(cfg)
        self._pool[k] = (client, cfg)
        return client

    def close_all(self) -> None:
        for client, cfg in list(self._pool.values()):
            try:
                client.close()
            except Exception:
                pass
            # Zero credentials
            cfg.password = None
            cfg.passphrase = None
        self._pool.clear()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_pool.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/ssh.py \
        tests/mcp/netcdf-reader/unit/test_ssh_pool.py
git commit -m "paths/ssh: session-scoped connection pool with credential zeroing"
```

---

### Task 36: SFTP file-like wrapper for xarray

**Files:**
- Modify: `src/mcp/netcdf-reader/paths/ssh.py`
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_sftp_open.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_sftp_open.py
from unittest.mock import MagicMock, patch
from src.mcp.netcdf_reader.paths.ssh import open_sftp_file


def test_open_sftp_file_returns_handle():
    fake_client = MagicMock()
    fake_sftp = MagicMock()
    fake_handle = MagicMock()
    fake_client.open_sftp.return_value = fake_sftp
    fake_sftp.open.return_value = fake_handle
    h = open_sftp_file(fake_client, "/remote/x.nc")
    assert h is fake_handle
    fake_sftp.open.assert_called_with("/remote/x.nc", "rb")


def test_open_sftp_file_supports_random_access():
    """h5netcdf needs seek + tell + read on the file-like."""
    fake_client = MagicMock()
    fake_handle = MagicMock()
    fake_handle.read.return_value = b"data"
    fake_handle.tell.return_value = 0
    fake_client.open_sftp.return_value.open.return_value = fake_handle
    h = open_sftp_file(fake_client, "/x.nc")
    assert h.read(4) == b"data"
    h.seek(100)
    fake_handle.seek.assert_called_with(100)
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_sftp_open.py -v
```

Expected: ImportError.

- [ ] **Step 3: Append `open_sftp_file` to `ssh.py`**

```python
# Append to src/mcp/netcdf-reader/paths/ssh.py
def open_sftp_file(client: paramiko.SSHClient, remote_path: str):
    """Return a file-like handle for the remote NetCDF file. h5netcdf
    can read directly from this (it requires seek/tell/read)."""
    sftp = client.open_sftp()
    return sftp.open(remote_path, "rb")
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_sftp_open.py -v
```

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/paths/ssh.py \
        tests/mcp/netcdf-reader/unit/test_ssh_sftp_open.py
git commit -m "paths/ssh: SFTP file-like wrapper for xarray h5netcdf engine"
```

---

### Task 37: Wire SSH into adapter and `inspect()` (silent path only)

**Files:**
- Modify: `src/mcp/netcdf-reader/adapter.py`
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Create: `tests/mcp/netcdf-reader/unit/test_ssh_inspect.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
from unittest.mock import MagicMock, patch
import xarray as xr
import numpy as np
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def _make_synthetic_dataset():
    return xr.Dataset(
        {"v": (("time", "lat", "lon"),
               np.zeros((1, 2, 2), dtype="float32"))},
        coords={"time": np.array(["2024-09-01"], dtype="datetime64[D]"),
                "lat": [0.0, 1.0], "lon": [0.0, 1.0]},
        attrs={"Conventions": "CF-1.7"},
    )


def test_ssh_inspect_succeeds_with_silent_auth(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()

    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               return_value=(fake_client, [])), \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset",
               return_value=_make_synthetic_dataset()):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["kind"] == "ssh_remote"
    assert env["result"]["convention"]["primary"] == "CF"
```

- [ ] **Step 2: Run to verify fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v
```

Expected: error (SSH path not yet wired through adapter).

- [ ] **Step 3: Update `adapter.open` to handle SSH paths via the pool**

In `adapter.py`, modify the `open` method:

```python
    def open(self, paths: list[str], file_objects: list[Any] | None = None) -> xr.Dataset:
        from src.mcp.netcdf_reader.paths.classify import classify, PathKind

        if file_objects:
            if len(file_objects) != 1:
                raise NotImplementedError("multi-file SSH not yet wired")
            return xr.open_dataset(file_objects[0], engine="h5netcdf",
                                   decode_times=True, chunks="auto")

        if len(paths) == 1:
            cls = classify(paths[0])
            if cls.kind == PathKind.SSH_REMOTE:
                from src.mcp.netcdf_reader.paths.ssh import (
                    SSHConfig, parse_ssh_config_for_host,
                    silent_auth_chain, open_sftp_file,
                )
                cfg = parse_ssh_config_for_host(cls.host)
                if cls.user:
                    cfg.user = cls.user
                if cls.port:
                    cfg.port = cls.port
                client, _attempts = silent_auth_chain(cfg)
                handle = open_sftp_file(client, cls.remote_path)
                return xr.open_dataset(handle, engine="h5netcdf",
                                       decode_times=True, chunks="auto")
            return xr.open_dataset(paths[0], decode_times=True, chunks="auto")

        from src.mcp.netcdf_reader.paths.multi_file import open_multi_file
        return open_multi_file(paths)
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/adapter.py \
        tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
git commit -m "adapter: route ssh:// paths through silent_auth_chain + SFTP"
```

---

### Task 38: SSH credential-prompt envelope (failure path)

**Files:**
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_ssh_inspect.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
from src.mcp.netcdf_reader.paths.ssh import SSHAuthNeeded, SSHConfig, AuthAttempt


def test_ssh_inspect_returns_ambiguity_when_silent_fails(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = SSHConfig(host="hpc.example.org", port=22, user="u")
    err = SSHAuthNeeded(cfg=cfg, attempts=[
        AuthAttempt("ssh_agent", "skipped", "no SSH_AUTH_SOCK"),
        AuthAttempt("default_identity_files", "no_keys"),
    ])
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               side_effect=err):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "ssh_auth_needed"
    cands = env["error"]["candidates"]
    assert any(c["param"] == "identity_file" for c in cands)
    assert any(c["param"] == "password" and c["sensitive"] is True for c in cands)
    assert env["error"]["retry_with_param"] == "ssh_config"
    assert env["error"]["context"]["host"] == "hpc.example.org"
    assert env["error"]["context"]["user"] == "u"
    assert "tried" in env["error"]["context"]


def test_ssh_inspect_handles_auth_failed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.netcdf_reader.paths.ssh import SSHAuthFailed
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               side_effect=SSHAuthFailed("denied")):
        env = inspect("ssh://hpc.example.org/data.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is False
    # silent chain failure raised SSHAuthFailed (rare); should still be
    # converted to ssh_auth_needed envelope so the user can retry.
    assert env["error"]["code"] in ("ambiguous", "ssh_auth_failed")
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v -k auth
```

Expected: `SSHAuthNeeded` exception leaks unhandled.

- [ ] **Step 3: Wrap SSH errors in `inspect()` envelope**

In `tools/inspect.py`, expand the `except` block where `adapter.open` is called:

```python
    try:
        ds = adapter.open(cls.paths)
    except FileNotFoundError as e:
        return envelope.error(envelope.ErrorCode.FILE_NOT_FOUND,
                              str(e), context={"path": path})
    except OSError as e:
        msg = str(e)
        code = (envelope.ErrorCode.REMOTE_FILE_NOT_FOUND
                if cls.kind in ("remote_url", "ssh_remote")
                else envelope.ErrorCode.FILE_NOT_FOUND)
        return envelope.error(code, msg, context={"path": path})
    except Exception as e:
        # Catch SSHAuthNeeded / SSHAuthFailed without importing at top
        # to keep paths/ssh.py optional for users who don't need SSH
        from src.mcp.netcdf_reader.paths.ssh import (
            SSHAuthNeeded, SSHAuthFailed,
        )
        if isinstance(e, SSHAuthNeeded):
            return _ssh_auth_needed_envelope(e)
        if isinstance(e, SSHAuthFailed):
            return _ssh_auth_failed_envelope(cls, str(e))
        return envelope.error(envelope.ErrorCode.INTERNAL_ERROR,
                              repr(e), context={"path": path})
```

Add helper functions to `tools/inspect.py`:

```python
def _ssh_auth_needed_envelope(err: "SSHAuthNeeded") -> dict[str, Any]:
    cfg = err.cfg
    candidates = [
        {"value": "identity_file", "label": "Path to a private key file",
         "param": "identity_file", "sensitive": False, "evidence": [],
         "confidence": 0.5},
        {"value": "password",
         "label": "Password (in-memory only, not stored)",
         "param": "password", "sensitive": True, "evidence": [],
         "confidence": 0.5},
        {"value": "ssh_config_alias",
         "label": "Use a ~/.ssh/config alias",
         "param": "ssh_alias", "sensitive": False, "evidence": [],
         "confidence": 0.5},
    ]
    tried = [
        {"method": a.method, "result": a.result, "detail": a.detail}
        for a in err.attempts
    ]
    return envelope.ambiguous(
        subcode=envelope.AmbiguitySubcode.SSH_AUTH_NEEDED,
        message=f"SSH authentication needed for {cfg.user}@{cfg.host}",
        candidates=candidates,
        prompt=(f"SSH auth needed for {cfg.user}@{cfg.host}. "
                f"Pick a method to authenticate."),
        retry_with_param="ssh_config",
        context={
            "host": cfg.host, "port": cfg.port, "user": cfg.user,
            "tried": tried, "may_need_jump_host": err.may_need_jump_host,
        },
    )


def _ssh_auth_failed_envelope(cls, msg: str) -> dict[str, Any]:
    # On wrong creds, route back to the prompt so the user can retry.
    candidates = [
        {"value": "password", "label": "Re-enter password",
         "param": "password", "sensitive": True, "evidence": [],
         "confidence": 0.5},
        {"value": "identity_file", "label": "Try a different key file",
         "param": "identity_file", "sensitive": False, "evidence": [],
         "confidence": 0.5},
    ]
    return envelope.ambiguous(
        subcode=envelope.AmbiguitySubcode.SSH_AUTH_NEEDED,
        message=f"SSH auth failed: {msg}",
        candidates=candidates,
        prompt=f"SSH auth was rejected. Pick a different method.",
        retry_with_param="ssh_config",
        context={"host": cls.host, "user": cls.user, "previous_error": msg},
    )
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v
```

Expected: all green.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/inspect.py \
        tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
git commit -m "ssh: wire SSHAuthNeeded/Failed → ambiguity envelope in inspect"
```

---

### Task 39: Explicit SSH config retry path

**Files:**
- Modify: `src/mcp/netcdf-reader/adapter.py`
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Modify: `src/mcp/netcdf-reader/tools/resolve_spec.py`
- Modify: `src/mcp/netcdf-reader/tools/read_slice.py`
- Modify: `src/mcp/netcdf-reader/tools/peek.py`
- Modify: `src/mcp/netcdf-reader/tools/compute_stats.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_ssh_inspect.py`

- [ ] **Step 1: Append failing test for `ssh_config` retry**

```python
# Append to tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
def test_ssh_inspect_retry_with_explicit_ssh_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()
    with patch("src.mcp.netcdf_reader.paths.ssh.connect_explicit",
               return_value=fake_client) as ce, \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset",
               return_value=_make_synthetic_dataset()):
        env = inspect(
            "ssh://hpc.example.org/data.nc",
            adapter=NetCDFAdapter(),
            ssh_config={
                "user": "u", "host": "hpc.example.org", "port": 22,
                "auth": {"method": "password", "password": "secret"},
            },
        )
    assert env["ok"] is True
    # connect_explicit was called instead of silent_auth_chain
    ce.assert_called_once()
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v -k explicit_ssh_config
```

Expected: `inspect()` doesn't accept `ssh_config` kwarg.

- [ ] **Step 3: Add `ssh_config` parameter through the call chain**

`tools/inspect.py`:

```python
def inspect(
    path: str, *,
    adapter: FormatAdapter,
    ssh_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # ... existing classify + cache lookup unchanged ...

    try:
        ds = adapter.open(cls.paths, ssh_config=ssh_config)
    # ... rest unchanged ...
```

`adapter.py` — extend `open` signature:

```python
    def open(
        self, paths: list[str], file_objects: list[Any] | None = None,
        ssh_config: dict[str, Any] | None = None,
    ) -> xr.Dataset:
        # ... when path is SSH:
        if cls.kind == PathKind.SSH_REMOTE:
            from src.mcp.netcdf_reader.paths.ssh import (
                SSHConfig, parse_ssh_config_for_host,
                silent_auth_chain, connect_explicit, open_sftp_file,
            )
            if ssh_config:
                cfg = SSHConfig(
                    host=ssh_config.get("host") or cls.host,
                    port=ssh_config.get("port") or cls.port or 22,
                    user=ssh_config.get("user") or cls.user,
                )
                auth = ssh_config.get("auth", {})
                method = auth.get("method")
                if method == "password":
                    cfg.password = auth.get("password")
                elif method == "identity_file":
                    cfg.identity_file = auth.get("identity_file")
                    cfg.passphrase = auth.get("passphrase")
                client = connect_explicit(cfg)
            else:
                cfg = parse_ssh_config_for_host(cls.host)
                if cls.user:
                    cfg.user = cls.user
                if cls.port:
                    cfg.port = cls.port
                client, _attempts = silent_auth_chain(cfg)
            handle = open_sftp_file(client, cls.remote_path)
            return xr.open_dataset(handle, engine="h5netcdf",
                                   decode_times=True, chunks="auto")
```

- [ ] **Step 4: Plumb `ssh_config` through other tools (resolve_spec, read_slice, compute_stats, peek)**

In each tool's signature, add `ssh_config: dict[str, Any] | None = None` and pass it to `adapter.open(...)`. (The hand-mod pattern: every place currently calling `adapter.open(cls.paths)` becomes `adapter.open(cls.paths, ssh_config=ssh_config)`.) Update each tool's calls to internal `resolve_spec` to forward the same `ssh_config`.

For each of `resolve_spec`, `read_slice`, `compute_stats`, `peek`: add the parameter and forward.

- [ ] **Step 5: Verify all SSH-related tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v -k ssh
```

Expected: all green.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/netcdf-reader/adapter.py \
        src/mcp/netcdf-reader/tools/inspect.py \
        src/mcp/netcdf-reader/tools/resolve_spec.py \
        src/mcp/netcdf-reader/tools/read_slice.py \
        src/mcp/netcdf-reader/tools/compute_stats.py \
        src/mcp/netcdf-reader/tools/peek.py \
        tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
git commit -m "ssh: explicit ssh_config retry path through all tools"
```

---

### Task 40: Slow-remote-read warning

**Files:**
- Modify: `src/mcp/netcdf-reader/tools/inspect.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_ssh_inspect.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
import time
def test_slow_remote_read_emits_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_client = MagicMock()
    fake_handle = MagicMock()
    def slow_open(*args, **kwargs):
        time.sleep(0)  # we'll patch the timer instead
        return _make_synthetic_dataset()
    with patch("src.mcp.netcdf_reader.paths.ssh.silent_auth_chain",
               return_value=(fake_client, [])), \
         patch("src.mcp.netcdf_reader.paths.ssh.open_sftp_file",
               return_value=fake_handle), \
         patch("xarray.open_dataset", side_effect=slow_open), \
         patch("time.monotonic", side_effect=[0.0, 35.0, 35.0, 35.0]):
        env = inspect("ssh://hpc.example.org/x.nc",
                      adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert any(w["code"] == "slow_remote_read" for w in env["warnings"])
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v -k slow_remote
```

- [ ] **Step 3: Add timing wrapper in `inspect()` for remote opens**

```python
# In tools/inspect.py, modify the open path:
import time as _time

# Inside inspect(), when opening:
    t0 = _time.monotonic()
    try:
        ds = adapter.open(cls.paths, ssh_config=ssh_config)
    # ... existing except clauses ...
    elapsed = _time.monotonic() - t0
    warnings = []
    if elapsed > 30 and cls.kind in (PathKind.REMOTE_URL, PathKind.SSH_REMOTE):
        warnings.append(envelope.warn(
            envelope.WarningCode.SLOW_REMOTE_READ,
            f"open took {elapsed:.0f}s; consider sshfs / staging",
            context={"elapsed_seconds": elapsed},
        ))
```

Then return `envelope.success(result, warnings=warnings)` at the end.

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_ssh_inspect.py -v
```

Expected: green.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/tools/inspect.py \
        tests/mcp/netcdf-reader/unit/test_ssh_inspect.py
git commit -m "ssh: emit slow_remote_read warning when open >30s"
```

---

## Phase 11: MCP server wiring

End of phase: an MCP server registers all 8 tools, dispatches via JSON-RPC, runs the lifecycle hook on startup.

### Task 41: MCP server skeleton + tool registration

**Files:**
- Create: `src/mcp/netcdf-reader/server.py` (replace existing stub)
- Create: `tests/mcp/netcdf-reader/unit/test_server.py`

- [ ] **Step 1: Write failing tests for the dispatcher**

```python
# tests/mcp/netcdf-reader/unit/test_server.py
from src.mcp.netcdf_reader.server import dispatch, list_tool_names


def test_list_tool_names_exposes_all_8():
    names = set(list_tool_names())
    assert names == {
        "inspect", "resolve_spec", "regrid_to_centers",
        "peek", "read_slice", "compute_stats",
        "find_variables", "find_time",
    }


def test_dispatch_inspect_returns_envelope(cf_3d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = dispatch("inspect", {"path": str(cf_3d_file)})
    assert out["ok"] is True
    assert "convention" in out["result"]


def test_dispatch_unknown_tool_returns_error():
    out = dispatch("not_a_tool", {})
    assert out["ok"] is False
    assert "unknown" in out["error"]["message"].lower()


def test_dispatch_resolve_spec(cf_4d_file, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    out = dispatch("resolve_spec", {
        "path": str(cf_4d_file), "variable": "ta",
        "time": "2024-09-01T06:00",
    })
    assert out["ok"] is True
    assert out["result"]["variable"] == "ta"


def test_dispatch_find_variables(cf_4d_file):
    out = dispatch("find_variables", {
        "path": str(cf_4d_file), "hint": "temperature",
    })
    assert out["ok"] is True
    assert out["result"]["matches"][0]["name"] == "ta"
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_server.py -v
```

Expected: ImportError.

- [ ] **Step 3: Implement `server.py`**

```python
# src/mcp/netcdf-reader/server.py
"""MCP server entry point. Thin dispatch over the 8 callable tools.

Registers a Stop-style cleanup at startup that removes slice temp dirs
from previous sessions per the lifecycle hook in the spec.
"""
from __future__ import annotations

import asyncio
from typing import Any

from src.mcp.netcdf_reader import envelope, lifecycle
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools import (
    compute_stats as _stats,
    find as _find,
    inspect as _inspect,
    peek as _peek,
    read_slice as _slice,
    resolve_spec as _spec,
    transforms as _transforms,
)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:
    Server = None
    stdio_server = None
    types = None

_ADAPTER = NetCDFAdapter()


def list_tool_names() -> list[str]:
    return ["inspect", "resolve_spec", "regrid_to_centers",
            "peek", "read_slice", "compute_stats",
            "find_variables", "find_time"]


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Internal dispatcher used by the MCP wrapper and by tests."""
    try:
        if name == "inspect":
            return _inspect.inspect(adapter=_ADAPTER, **args)
        if name == "resolve_spec":
            return _spec.resolve_spec(adapter=_ADAPTER, **args)
        if name == "regrid_to_centers":
            return _transforms.regrid_to_centers(args["spec"])
        if name == "peek":
            return _peek.peek(adapter=_ADAPTER, **args)
        if name == "read_slice":
            return _slice.read_slice(adapter=_ADAPTER, **args)
        if name == "compute_stats":
            return _stats.compute_stats(adapter=_ADAPTER, **args)
        if name == "find_variables":
            return _find.find_variables(adapter=_ADAPTER, **args)
        if name == "find_time":
            return _find.find_time(adapter=_ADAPTER, **args)
        return envelope.error("unknown_tool", f"unknown tool: {name}",
                              context={"name": name})
    except TypeError as e:
        return envelope.error("internal_error",
                              f"bad arguments for {name}: {e}",
                              context={"args": list(args.keys())})


def _session_id_from_lifecycle() -> str:
    from src.mcp.netcdf_reader.tools.read_slice import _session_id
    return _session_id()


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install [mcp] extra")

    # Cleanup previous sessions' slice temp dirs at startup
    lifecycle.cleanup_old_slice_dirs(keep=_session_id_from_lifecycle())

    server = Server("netcdf-reader")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Any]:
        return [
            types.Tool(name=n, description=f"netcdf-reader.{n}",
                       inputSchema={"type": "object"})
            for n in list_tool_names()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
        result = dispatch(name, arguments or {})
        # MCP expects text content
        import json
        return [types.TextContent(type="text", text=json.dumps(result))]

    return server


def main() -> None:
    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install [mcp] extra")
    server = make_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_server.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/netcdf-reader/server.py \
        tests/mcp/netcdf-reader/unit/test_server.py
git commit -m "server: MCP dispatch over the 8 callable tools"
```

---

### Task 42: Lifecycle — close SSH pool on shutdown

**Files:**
- Modify: `src/mcp/netcdf-reader/server.py`
- Modify: `src/mcp/netcdf-reader/lifecycle.py`
- Modify: `tests/mcp/netcdf-reader/unit/test_lifecycle.py`

- [ ] **Step 1: Append failing test**

```python
# Append to tests/mcp/netcdf-reader/unit/test_lifecycle.py
from unittest.mock import MagicMock
from src.mcp.netcdf_reader.lifecycle import register_pool, on_shutdown


def test_on_shutdown_closes_registered_pools():
    pool = MagicMock()
    register_pool(pool)
    on_shutdown()
    pool.close_all.assert_called_once()
```

- [ ] **Step 2: Run — fails**

```bash
pytest tests/mcp/netcdf-reader/unit/test_lifecycle.py -v -k shutdown
```

- [ ] **Step 3: Add pool-registry to `lifecycle.py`**

```python
# Append to src/mcp/netcdf-reader/lifecycle.py
_POOLS: list[Any] = []


def register_pool(pool: Any) -> None:
    _POOLS.append(pool)


def on_shutdown() -> None:
    for p in _POOLS:
        try:
            p.close_all()
        except Exception:
            pass
    _POOLS.clear()
```

(Add `from typing import Any` if not present.)

- [ ] **Step 4: Wire `on_shutdown` into the server's main()**

In `server.py`, modify `main()`:

```python
def main() -> None:
    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install [mcp] extra")
    server = make_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            try:
                await server.run(read, write, server.create_initialization_options())
            finally:
                lifecycle.on_shutdown()

    asyncio.run(_run())
```

- [ ] **Step 5: Verify tests pass**

```bash
pytest tests/mcp/netcdf-reader/unit/test_lifecycle.py -v
```

Expected: green.

- [ ] **Step 6: Commit**

```bash
git add src/mcp/netcdf-reader/lifecycle.py \
        src/mcp/netcdf-reader/server.py \
        tests/mcp/netcdf-reader/unit/test_lifecycle.py
git commit -m "lifecycle: register and close SSH pools on shutdown"
```

---

## Phase 12: Polish, README, and the seam-discipline test

End of phase: README documents the tool surface and envelope shape; format-agnostic discipline is enforced by a smoke test; opt-in real-SSH integration scaffold lands.

### Task 43: README — tool list, envelope shape, install

**Files:**
- Replace: `src/mcp/netcdf-reader/README.md`

- [ ] **Step 1: Write README**

```markdown
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
ncplot-netcdf-reader   # via stdio MCP transport
```

Or wire from a Claude Code plugin manifest (cycle 4).

## Cache locations

- `.ncplot/inspections/<hash>.json` — persistent inspection cache (mtime-keyed)
- `.ncplot/slices/<session>/...` — session-scoped slice temp files (cleared at startup)

## Testing

```bash
pytest tests/mcp/netcdf-reader/unit/ -v          # synthetic fixtures, fast
NCPLOT_INTEGRATION=1 pytest tests/mcp/netcdf-reader/integration/ -m integration
NCPLOT_REAL_SSH=1 pytest tests/mcp/netcdf-reader/integration/ -m real_ssh
```

See `tests/mcp/netcdf-reader/REAL_SSH_SETUP.md` for real-SSH test setup.
```

- [ ] **Step 2: Commit**

```bash
git add src/mcp/netcdf-reader/README.md
git commit -m "README: tool list, envelope shape, install, schemes"
```

---

### Task 44: Seam-discipline smoke test

**Files:**
- Create: `tests/mcp/netcdf-reader/unit/test_seam.py`

- [ ] **Step 1: Write the seam test**

```python
# tests/mcp/netcdf-reader/unit/test_seam.py
"""Verify that ⤴ format-agnostic modules don't import format-specific
modules. When a second adapter (Zarr, GRIB, HDF5) is added in a future
cycle, this test ensures the format-agnostic bundle can be lifted to
_core/ without the lift dragging in NetCDF-specific code."""
from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest


PKG_ROOT = Path(__file__).resolve().parents[3] / "src" / "mcp" / "netcdf-reader"

# Files marked ⤴ format-agnostic in the spec
AGNOSTIC = {
    "envelope.py", "cache.py", "selectors.py", "lifecycle.py",
    "paths/classify.py", "paths/ssh.py",
    "conventions/cf.py",
    "tools/inspect.py", "tools/resolve_spec.py", "tools/read_slice.py",
    "tools/compute_stats.py", "tools/peek.py", "tools/find.py",
    "tools/transforms.py",
}

# Files known to be format-specific
SPECIFIC = {
    "adapter.py",
    "paths/multi_file.py",
    "conventions/wrf.py", "conventions/roms.py",
}


def _collect_imports(path: Path) -> set[str]:
    src = path.read_text()
    try:
        tree = ast.parse(src, str(path))
    except SyntaxError:
        return set()
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


def test_agnostic_modules_do_not_import_specific_modules():
    """Each ⤴ file must not import from a format-specific module."""
    violations: list[str] = []
    for rel in AGNOSTIC:
        f = PKG_ROOT / rel
        assert f.exists(), f"missing agnostic file: {rel}"
        imports = _collect_imports(f)
        for imp in imports:
            for spec in SPECIFIC:
                spec_module = spec.replace("/", ".").removesuffix(".py")
                if imp.endswith(spec_module):
                    violations.append(f"{rel} imports {imp}")
    if violations:
        pytest.fail("seam violations:\n" + "\n".join(violations))


def test_agnostic_files_have_marker_comment():
    """Each ⤴ file should have the marker comment in the docstring or top."""
    missing: list[str] = []
    for rel in AGNOSTIC:
        f = PKG_ROOT / rel
        text = f.read_text()
        # Check the first 800 chars
        if "⤴" not in text[:800]:
            missing.append(rel)
    if missing:
        pytest.fail(
            f"⤴ marker missing from: {missing}. Add a header comment "
            f"(e.g. '\"\"\"⤴ format-agnostic — eligible for _core/ lift.\"\"\"')."
        )
```

- [ ] **Step 2: Run — fails on the marker check until all files have it**

```bash
pytest tests/mcp/netcdf-reader/unit/test_seam.py -v
```

If the import-discipline test fails, fix the offending file by either (a) moving the imported symbol to a format-agnostic module or (b) lazy-importing inside the function rather than at module top.

If the marker test fails, add the docstring marker to each named file.

- [ ] **Step 3: Run all unit tests**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: all green.

- [ ] **Step 4: Commit**

```bash
git add tests/mcp/netcdf-reader/unit/test_seam.py
git commit -m "tests/seam: enforce format-agnostic vs format-specific discipline"
```

---

### Task 45: Real-SSH integration test scaffold

**Files:**
- Create: `tests/mcp/netcdf-reader/integration/test_real_ssh.py`
- Create: `tests/mcp/netcdf-reader/REAL_SSH_SETUP.md`
- Create: `tests/mcp/netcdf-reader/integration/conftest.py`
- Modify: project root: ensure `.env.test` is gitignored

- [ ] **Step 1: Add `.env.test` to `.gitignore` if missing**

```bash
grep -q '.env.test' .gitignore || echo '.env.test' >> .gitignore
```

- [ ] **Step 2: Create `tests/mcp/netcdf-reader/integration/conftest.py`**

```python
# tests/mcp/netcdf-reader/integration/conftest.py
"""Integration-tier conftest. Loads optional .env.test from repo root."""
from __future__ import annotations

import os
from pathlib import Path

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: pinned-real-files")
    config.addinivalue_line("markers", "real_ssh: real SSH endpoint")


@pytest.fixture(autouse=True, scope="session")
def _load_env_test():
    p = Path(__file__).resolve().parents[4] / ".env.test"
    if p.exists():
        for line in p.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k, v)
```

- [ ] **Step 3: Write the real-SSH integration test**

```python
# tests/mcp/netcdf-reader/integration/test_real_ssh.py
"""Opt-in: run against a real SSH endpoint configured via env vars.

Required env vars:
  NCPLOT_REAL_SSH_HOST          remote hostname or ~/.ssh/config alias
  NCPLOT_REAL_SSH_USER          remote username
  NCPLOT_REAL_SSH_FIXTURE_PATH  absolute path to a small NetCDF on the remote

Optional env vars:
  NCPLOT_REAL_SSH_PORT          (default 22)
  NCPLOT_REAL_SSH_KEY_PATH      identity file (otherwise silent chain is tried)
  NCPLOT_REAL_SSH_PASSWORD      via .env.test (gitignored). Discouraged.
"""
from __future__ import annotations

import os
import re

import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect
from src.mcp.netcdf_reader.tools.read_slice import read_slice


pytestmark = [
    pytest.mark.real_ssh,
    pytest.mark.skipif(
        os.environ.get("NCPLOT_REAL_SSH") != "1",
        reason="set NCPLOT_REAL_SSH=1 to run",
    ),
]


def _ssh_url() -> str:
    host = os.environ["NCPLOT_REAL_SSH_HOST"]
    user = os.environ["NCPLOT_REAL_SSH_USER"]
    port = os.environ.get("NCPLOT_REAL_SSH_PORT", "22")
    path = os.environ["NCPLOT_REAL_SSH_FIXTURE_PATH"]
    return f"ssh://{user}@{host}:{port}{path}"


def _ssh_config_explicit() -> dict | None:
    """Build explicit ssh_config kwarg if NCPLOT_REAL_SSH_KEY_PATH set."""
    if "NCPLOT_REAL_SSH_KEY_PATH" in os.environ:
        return {
            "user": os.environ["NCPLOT_REAL_SSH_USER"],
            "host": os.environ["NCPLOT_REAL_SSH_HOST"],
            "port": int(os.environ.get("NCPLOT_REAL_SSH_PORT", 22)),
            "auth": {"method": "identity_file",
                     "identity_file": os.environ["NCPLOT_REAL_SSH_KEY_PATH"]},
        }
    if "NCPLOT_REAL_SSH_PASSWORD" in os.environ:
        return {
            "user": os.environ["NCPLOT_REAL_SSH_USER"],
            "host": os.environ["NCPLOT_REAL_SSH_HOST"],
            "port": int(os.environ.get("NCPLOT_REAL_SSH_PORT", 22)),
            "auth": {"method": "password",
                     "password": os.environ["NCPLOT_REAL_SSH_PASSWORD"]},
        }
    return None


def test_inspect_real_ssh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                  ssh_config=_ssh_config_explicit())
    assert env["ok"] is True, env
    assert env["result"]["kind"] == "ssh_remote"


def test_read_slice_real_ssh(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env_inspect = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                          ssh_config=_ssh_config_explicit())
    var = env_inspect["result"]["variables"][0]["name"]
    env = read_slice(_ssh_url(), variable=var,
                     adapter=NetCDFAdapter(),
                     ssh_config=_ssh_config_explicit())
    assert env["ok"] is True, env


def test_password_never_appears_in_capsys(capsys, tmp_path, monkeypatch):
    if "NCPLOT_REAL_SSH_PASSWORD" not in os.environ:
        pytest.skip("password not configured")
    monkeypatch.chdir(tmp_path)
    inspect(_ssh_url(), adapter=NetCDFAdapter(),
            ssh_config=_ssh_config_explicit())
    out = capsys.readouterr()
    pw = os.environ["NCPLOT_REAL_SSH_PASSWORD"]
    assert pw not in out.out
    assert pw not in out.err


def test_no_password_in_slice_temp_files(tmp_path, monkeypatch):
    if "NCPLOT_REAL_SSH_PASSWORD" not in os.environ:
        pytest.skip("password not configured")
    monkeypatch.chdir(tmp_path)
    env_inspect = inspect(_ssh_url(), adapter=NetCDFAdapter(),
                          ssh_config=_ssh_config_explicit())
    var = env_inspect["result"]["variables"][0]["name"]
    read_slice(_ssh_url(), variable=var, adapter=NetCDFAdapter(),
               ssh_config=_ssh_config_explicit(),
               max_inline_bytes=1)  # force file form
    pw = os.environ["NCPLOT_REAL_SSH_PASSWORD"]
    for f in (tmp_path / ".ncplot").rglob("*"):
        if f.is_file():
            try:
                content = f.read_bytes()
            except Exception:
                continue
            assert pw.encode() not in content, f"password leaked in {f}"
```

- [ ] **Step 4: Write `REAL_SSH_SETUP.md`**

```markdown
# Real-SSH integration tests

These tests run only when `NCPLOT_REAL_SSH=1` is set. They verify that
the SSH path works against a real remote endpoint of your choosing.

## Setup

1. Pick a remote host you can SSH into. (Localhost SSH is fine — `sshd`
   on macOS / Linux works.)
2. Place a small NetCDF file on that remote (e.g., `/tmp/fixture.nc`).
   You can generate one with:

   ```python
   import xarray as xr, numpy as np
   ds = xr.Dataset(
       {"v": (("t", "lat", "lon"),
              np.random.default_rng(0).normal(size=(3, 5, 6)).astype("f4"))},
       coords={"t": np.array(["2024-01-01", "2024-01-02", "2024-01-03"], dtype="datetime64[D]"),
               "lat": np.linspace(-30, 30, 5), "lon": np.linspace(-60, 60, 6)},
       attrs={"Conventions": "CF-1.7"},
   )
   ds.to_netcdf("/tmp/fixture.nc")
   ```

3. Configure env vars. Either export inline:

   ```bash
   export NCPLOT_REAL_SSH=1
   export NCPLOT_REAL_SSH_HOST=localhost
   export NCPLOT_REAL_SSH_USER=$USER
   export NCPLOT_REAL_SSH_FIXTURE_PATH=/tmp/fixture.nc
   export NCPLOT_REAL_SSH_KEY_PATH=$HOME/.ssh/id_ed25519  # optional
   ```

   Or write `.env.test` at the repo root (gitignored):

   ```ini
   NCPLOT_REAL_SSH=1
   NCPLOT_REAL_SSH_HOST=localhost
   NCPLOT_REAL_SSH_USER=youngsung
   NCPLOT_REAL_SSH_FIXTURE_PATH=/tmp/fixture.nc
   NCPLOT_REAL_SSH_KEY_PATH=/home/youngsung/.ssh/id_ed25519
   ```

4. Run:

   ```bash
   pytest tests/mcp/netcdf-reader/integration/test_real_ssh.py -v -m real_ssh
   ```

## Notes

- If you want to test password auth, set `NCPLOT_REAL_SSH_PASSWORD` in
  `.env.test` (NEVER inline on the command line). The credential-redaction
  property tests verify the password never lands in test output or any
  cache file.
- The opt-in marker (`pytest -m real_ssh`) prevents these tests from
  running in CI by default.
- Localhost SSH is the easiest setup. macOS: System Preferences → Sharing
  → Remote Login. Linux: `sudo systemctl enable --now sshd`.
```

- [ ] **Step 5: Verify the test scaffolding skips correctly when not configured**

```bash
pytest tests/mcp/netcdf-reader/integration/test_real_ssh.py -v
```

Expected: skipped (no `NCPLOT_REAL_SSH=1`).

- [ ] **Step 6: Commit**

```bash
git add .gitignore \
        tests/mcp/netcdf-reader/integration/test_real_ssh.py \
        tests/mcp/netcdf-reader/integration/conftest.py \
        tests/mcp/netcdf-reader/REAL_SSH_SETUP.md
git commit -m "tests: real-SSH integration scaffold (opt-in via NCPLOT_REAL_SSH=1)"
```

---

### Task 46: Pinned-real-files integration scaffold

**Files:**
- Create: `tests/mcp/netcdf-reader/integration/test_real_files.py`
- Create: `tests/mcp/netcdf-reader/integration/download_samples.sh`
- Modify: `.gitignore`

- [ ] **Step 1: Add `tests/mcp/netcdf-reader/integration/data/` to `.gitignore`**

```bash
grep -q 'tests/mcp/netcdf-reader/integration/data' .gitignore || \
  echo 'tests/mcp/netcdf-reader/integration/data/' >> .gitignore
```

- [ ] **Step 2: Write the integration test**

```python
# tests/mcp/netcdf-reader/integration/test_real_files.py
"""Opt-in: pinned real-sample integration tests.

Requires running tests/mcp/netcdf-reader/integration/download_samples.sh
once to populate tests/mcp/netcdf-reader/integration/data/.
"""
from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("NCPLOT_INTEGRATION") != "1",
        reason="set NCPLOT_INTEGRATION=1 to run",
    ),
]

DATA = Path(__file__).parent / "data"


@pytest.mark.skipif(not (DATA / "wrfout_sample.nc").exists(),
                    reason="run download_samples.sh first")
def test_inspect_real_wrf(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(DATA / "wrfout_sample.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["convention"]["primary"] == "WRF"


@pytest.mark.skipif(not (DATA / "era5_t2m_sample.nc").exists(),
                    reason="run download_samples.sh first")
def test_inspect_real_era5(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = inspect(str(DATA / "era5_t2m_sample.nc"), adapter=NetCDFAdapter())
    assert env["ok"] is True
    assert env["result"]["convention"]["primary"] in ("CF", "CMIP")
```

- [ ] **Step 3: Write the download placeholder script**

```bash
#!/usr/bin/env bash
# tests/mcp/netcdf-reader/integration/download_samples.sh
#
# Populate tests/mcp/netcdf-reader/integration/data/ with small real
# samples for integration testing. Replace these URLs with samples you
# have rights to. Files land in a gitignored directory.
set -euo pipefail
DIR="$(cd "$(dirname "$0")" && pwd)/data"
mkdir -p "$DIR"

# Replace with actual URLs you control or have rights to
# curl -L -o "$DIR/wrfout_sample.nc" "https://example.org/wrfout_small.nc"
# curl -L -o "$DIR/era5_t2m_sample.nc" "https://example.org/era5_t2m_small.nc"

echo "Edit this script with the URLs of your sample files,"
echo "then re-run to populate $DIR."
```

- [ ] **Step 4: Make the script executable**

```bash
chmod +x tests/mcp/netcdf-reader/integration/download_samples.sh
```

- [ ] **Step 5: Verify it skips cleanly without samples**

```bash
NCPLOT_INTEGRATION=1 pytest tests/mcp/netcdf-reader/integration/test_real_files.py -v
```

Expected: skipped (no fixture data).

- [ ] **Step 6: Commit**

```bash
git add .gitignore \
        tests/mcp/netcdf-reader/integration/test_real_files.py \
        tests/mcp/netcdf-reader/integration/download_samples.sh
git commit -m "tests: pinned real-files integration scaffold"
```

---

### Task 47: Final lint + typecheck + full suite green

**Files:**
- (no new files; sweep)

- [ ] **Step 1: Run ruff over the whole package**

```bash
ruff check src/mcp/netcdf-reader/ tests/mcp/netcdf-reader/
```

Fix any issues with minimal targeted edits.

- [ ] **Step 2: Run mypy**

```bash
mypy src/mcp/netcdf-reader/
```

Fix any type errors.

- [ ] **Step 3: Run the full test suite**

```bash
pytest tests/mcp/netcdf-reader/unit/ -v
```

Expected: all unit tests pass (~120 tests across envelope, selectors, cache, classify, conventions/cf/wrf/roms, inspect, resolve_spec, read_slice, compute_stats, peek, find, transforms, multi_file, ssh_*, server, lifecycle, seam).

- [ ] **Step 4: Hand-run the MCP server briefly**

```bash
echo "smoke test: server should start, list tools, and exit on EOF"
timeout 2 ncplot-netcdf-reader </dev/null || true
```

Expected: starts without import errors. (Will exit on EOF; that's fine.)

- [ ] **Step 5: Final commit**

```bash
git add -A
git diff --cached --quiet || git commit -m "phase-12 final lint/typecheck/test sweep"
```

---

## Self-Review

After Task 47, run a self-review pass against the spec:

- [ ] **Spec coverage check.** Open `docs/specs/2026-05-06-cycle-1-netcdf-reader.md` side by side with the implementation. For each spec section, confirm at least one task implements it:
  - §2 Tool surface (8 callable + lifecycle hook) — Tasks 12, 14–21, 41
  - §3 D/C-path split — implicit in tools/* organization
  - §4 Convention detection — Tasks 10, 11, 26–30
  - §5 Selector grammar — Tasks 4, 14
  - §6 Path handling — Tasks 6, 22–24, 31, 32–40
  - §7 SSH credential flow — Tasks 32–40
  - §8 Caching — Tasks 5, 12, 16, 17
  - §9 Response envelope — Tasks 2, 3, 38
  - §10 Tool output schemas — Tasks 12, 14–21
  - §11 Multi-format extension seam — Tasks 9, 44
  - §12 Testing strategy — every test task; Tasks 45, 46 for opt-in tiers
  - §13 Module layout — established by Task 1; verified by Task 44

- [ ] **Lifecycle hook from spec §2** — verified in Task 42 (`on_shutdown` closes pools, `cleanup_old_slice_dirs` runs at startup).

- [ ] **Cross-cutting principle: "ask when ambiguous, never silently guess"** — verified in Tasks 10 (CF candidates), 14 (variable + time candidates), 38 (SSH auth candidates).

- [ ] **Cross-cutting principle: "echo every resolved value"** — verified in Task 14 (`resolved` field in resolve_spec output).

- [ ] **Security guarantee: credentials never on disk / in logs** — verified in Tasks 34 (`test_password_not_logged`), 35 (`test_pool_zeros_credentials_on_close`), 45 (`test_password_never_appears_in_capsys`, `test_no_password_in_slice_temp_files`).

- [ ] **Default `max_inline_bytes = 100_000` (per spec §10)** — verified in Task 15's signature.

- [ ] **Percentiles 5/50/95 (per spec §10)** — verified in Task 18.

- [ ] **`peek` 10 KB hard cap (per spec §10)** — verified in Task 19's `PEEK_HARD_CAP_BYTES` constant + test.

If any spec section is uncovered, add a task before this self-review section.

---

## Plan complete

Plan saved to `docs/plans/2026-05-06-cycle-1-netcdf-reader.md`. Two execution options:

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Required sub-skill: `superpowers:subagent-driven-development`.

**2. Inline Execution** — Execute tasks in this session using `superpowers:executing-plans`, batch execution with checkpoints.

Which approach?


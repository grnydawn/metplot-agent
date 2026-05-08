# Cycle 2: `plot-renderer` MCP — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `plot-renderer` MCP server per `docs/specs/2026-05-07-cycle-2-plot-renderer.md`. End state: an MCP server that exposes 3 callable tools (`render_map`, `render_timeseries`, `render_profile`) which turn structured plot specs into static PNG/PDF/SVG figure files, with a render-oracle JSON for tests, a deterministic style-template feature for plot-from-reference workflows, and graceful degradation when cartopy is missing.

**Architecture:** One MCP server organized as `core (envelope, defaults, colormap_registry, protocols) + adapter (inline + slice_loader) + safety + style + lifecycle + oracle + tools (render_map / render_timeseries / render_profile)`. Format-agnostic modules are tagged `⤴` and importable without NetCDF assumptions. The slice-file loader is the *only* format-specific module; cartopy is contained to `tools/render_map.py`. TDD: failing test → minimal implementation → green → commit. Frequent commits.

**Tech Stack:** Python 3.10+, `matplotlib`, `numpy`, `xarray`, `h5netcdf`, `dask[array]`, `mcp`, `pytest`, `ruff`, `mypy`. Optional: `cartopy` (maps), `scipy` (lowess trendline), `scikit-image` (SSIM image-diff).

**Before starting:** the `cycle-2-plot-renderer` branch is already created from master. Verify with `git branch --show-current`.

> **⚠ Naming convention.** Same as cycle 1: on-disk Python package uses underscore (`src/mcp/plot_renderer/`); MCP server external name uses hyphen (`plot-renderer`). Test paths likewise use `tests/mcp/plot_renderer/`. The existing scaffold at `src/mcp/plot-renderer/` (hyphen) is overwritten in Task 1.
>
> **In every "Files:" list and `git add` command in this plan, the on-disk path is `plot_renderer` (underscore).**

---

## File Structure

### Source files (`src/mcp/plot_renderer/`)

| File | Responsibility | Format-agnostic? |
|------|----------------|-------------------|
| `pyproject.toml` | Package metadata + deps | n/a |
| `README.md` | Tool list, envelope shape, install | n/a |
| `__init__.py` | Package marker | n/a |
| `server.py` | Thin MCP dispatch | ⤴ YES |
| `envelope.py` | Success/error/ambiguity envelopes (copy from cycle 1) | ⤴ YES |
| `defaults.py` | `LIBRARY_DEFAULTS` dict | ⤴ YES |
| `colormap_registry.py` | matplotlib cmap validation, lazy-loaded | ⤴ YES |
| `protocols.py` | `SliceLoader` Protocol; `__format_specific__` marker pattern | ⤴ YES |
| `adapter.py` | Spec → typed numpy arrays + DataArray | ⤴ YES |
| `slice_loader.py` | NetCDF-only loader; `__format_specific__ = True` | NO |
| `style.py` | `style_template` application + mapping table | ⤴ YES |
| `safety.py` | downsample, NaN, lon-shift, constant-field, all-NaN, percentile-clip | ⤴ YES |
| `oracle.py` | render-oracle JSON capture from `Figure` | ⤴ YES |
| `lifecycle.py` | output path resolution, auto-name, atomic save | ⤴ YES |
| `tools/__init__.py` | Package marker | n/a |
| `tools/render_map.py` | cartopy-aware map drawing | NO (cartopy) |
| `tools/render_timeseries.py` | line plotting, multi-series, trendlines | ⤴ YES |
| `tools/render_profile.py` | vertical profile, pressure-invert, log-scale | ⤴ YES |

### Test files (`tests/mcp/plot_renderer/`)

| File | What it covers |
|------|----------------|
| `conftest.py` | Fixtures + `matplotlib.use("Agg")` global |
| `unit/test_envelope.py` | success/error/ambiguous shapes |
| `unit/test_defaults.py` | LIBRARY_DEFAULTS shape |
| `unit/test_colormap_registry.py` | valid/invalid cmap lookup |
| `unit/test_adapter_inline.py` | inline-form normalization, NaN encoding round-trip |
| `unit/test_adapter_slice_ref.py` | slice_ref form via slice_loader |
| `unit/test_slice_loader.py` | NetCDF loader unit tests |
| `unit/test_safety_downsample.py` | threshold + override |
| `unit/test_safety_nan.py` | NaN mask + all-NaN ambiguity + high_nan_fraction |
| `unit/test_safety_lon_shift.py` | 0..360 ↔ -180..180 |
| `unit/test_safety_constant.py` | constant-field warning + percentile clip |
| `unit/test_style_application.py` | mapping rows + precedence + trace |
| `unit/test_style_template_unknown.py` | unknown fields → fields_ignored |
| `unit/test_lifecycle_output_path.py` | explicit, auto-name, parent dir, atomic write |
| `unit/test_oracle_schema.py` | schema completeness for each tool |
| `unit/test_render_timeseries.py` | single + multi-series + trendline |
| `unit/test_render_profile.py` | pressure-invert, log scale, multi-series |
| `unit/test_render_map.py` | with cartopy |
| `unit/test_render_map_no_cartopy.py` | monkeypatched ImportError → ambiguity envelope |
| `unit/test_seam.py` | format-agnostic + cartopy isolation |
| `integration/test_pipeline_inline.py` | inline e2e: spec → PNG + oracle |
| `integration/test_pipeline_slice_ref.py` | file-form e2e |
| `integration/test_three_tools_smoke.py` | each tool produces PNG |
| `integration/test_image_diff_optional.py` | gated `--image-diff` SSIM suite |
| `integration/test_real_files.py` | gated `NCPLOT_REAL_FILES=1` real-data scaffold |

`tests/golden/` holds committed reference PNGs for the image-diff suite.

---

## Phase 1: Foundation

Phase 1 lays the cross-cutting types every later module imports. No
matplotlib drawing yet, no spec parsing — just the envelope shape, the
library defaults, and the colormap registry.

### Task 1: Set up package skeleton

**Files:**
- Modify: `src/mcp/plot-renderer/` → rename to `src/mcp/plot_renderer/`
- Create: `src/mcp/plot_renderer/__init__.py`
- Create: `src/mcp/plot_renderer/pyproject.toml`
- Modify: `.gitignore` (add `.ncplot/figures/`)
- Create: `tests/mcp/plot_renderer/__init__.py`
- Create: `tests/mcp/plot_renderer/conftest.py`
- Create: `tests/mcp/plot_renderer/unit/__init__.py`

- [ ] **Step 1: Rename the hyphenated stub directory and stage the rename**

```bash
git mv src/mcp/plot-renderer src/mcp/plot_renderer
git status --short
```

Expected: existing scaffold files renamed, no content change yet.

- [ ] **Step 2: Overwrite `__init__.py`**

```python
# src/mcp/plot_renderer/__init__.py
"""plot-renderer MCP — turns structured plot specs into static figures.

See docs/specs/2026-05-07-cycle-2-plot-renderer.md for the contract.
"""
```

- [ ] **Step 3: Overwrite `pyproject.toml`**

```toml
# src/mcp/plot_renderer/pyproject.toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "plot-renderer"
version = "0.1.0"
description = "MCP server: matplotlib/cartopy plot rendering from structured specs"
requires-python = ">=3.10"
dependencies = [
    "mcp>=1.0",
    "matplotlib>=3.8",
    "numpy>=1.24",
    "xarray>=2024.1",
    "h5netcdf>=1.3",
    "dask[array]>=2024.1",
]

[project.optional-dependencies]
maps  = ["cartopy>=0.22"]
trend = ["scipy>=1.11"]
dev   = ["pytest>=8", "ruff>=0.5", "mypy>=1.10", "scikit-image>=0.22"]

[project.scripts]
ncplot-plot-renderer = "src.mcp.plot_renderer.server:main"
```

- [ ] **Step 4: Add `.ncplot/figures/` to `.gitignore`**

Inspect `.gitignore` first. If `.ncplot/` already excluded everything (cycle 1 added `.ncplot/`), figures are already covered. Otherwise add a specific line.

```bash
grep -nE "^\.ncplot" .gitignore
```

If `.ncplot/` is already there, no change needed. If only `.ncplot/slices/` is there, append:

```
.ncplot/figures/
```

- [ ] **Step 5: Write `tests/mcp/plot_renderer/conftest.py`**

```python
# tests/mcp/plot_renderer/conftest.py
"""Shared fixtures for plot-renderer tests.

Forces the matplotlib Agg backend before any test imports matplotlib so
suite runs headless on CI.
"""
import os

# Set BEFORE any matplotlib import
os.environ.setdefault("MPLBACKEND", "Agg")

import matplotlib  # noqa: E402
matplotlib.use("Agg")  # idempotent

import numpy as np  # noqa: E402
import pytest  # noqa: E402
import xarray as xr  # noqa: E402


@pytest.fixture
def small_2d_dataset() -> xr.Dataset:
    """Tiny 2D lat/lon Dataset for map tests."""
    lat = np.linspace(-30.0, 30.0, 7)
    lon = np.linspace(-60.0, 60.0, 13)
    values = np.outer(np.cos(np.deg2rad(lat)),
                      np.sin(np.deg2rad(lon))).astype("float32")
    return xr.Dataset(
        {"v": (("lat", "lon"), values, {"units": "K", "long_name": "demo"})},
        coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                "lon": ("lon", lon, {"units": "degrees_east"})},
        attrs={"Conventions": "CF-1.7"},
    )


@pytest.fixture
def small_timeseries() -> dict:
    """Single-series spec sugar."""
    times = [f"2024-{m:02d}-15T00:00" for m in range(1, 13)]
    values = np.linspace(0.0, 11.0, 12).tolist()
    return {"values": values, "time": times, "label": "demo"}


@pytest.fixture
def small_profile() -> dict:
    """Single-series profile spec sugar."""
    vertical = [1000.0, 850.0, 700.0, 500.0, 250.0, 100.0]  # hPa
    values = [288.0, 280.0, 270.0, 250.0, 220.0, 200.0]
    return {"values": values, "vertical": vertical,
            "vertical_units": "hPa", "label": "demo"}
```

- [ ] **Step 6: Verify pytest can collect the empty test dir**

Run:

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

Expected: `collected 0 items` (no tests yet); no import errors.

- [ ] **Step 7: Commit**

```bash
git add src/mcp/plot_renderer/__init__.py \
        src/mcp/plot_renderer/pyproject.toml \
        .gitignore \
        tests/mcp/plot_renderer/__init__.py \
        tests/mcp/plot_renderer/conftest.py \
        tests/mcp/plot_renderer/unit/__init__.py
git commit -m "cycle-2 task 1: package skeleton + matplotlib Agg + fixtures"
```

---

### Task 2: Envelope helpers (copy from cycle 1)

**Files:**
- Create: `src/mcp/plot_renderer/envelope.py`
- Create: `tests/mcp/plot_renderer/unit/test_envelope.py`

The envelope shape is locked across all MCPs in this repo. We copy
cycle-1's `envelope.py` verbatim to avoid coupling the two packages.

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_envelope.py
from src.mcp.plot_renderer.envelope import (
    success, error, ambiguous, warn,
    ErrorCode, AmbiguitySubcode, WarningCode,
)


def test_success_shape():
    env = success({"path": "x.png"})
    assert env == {"ok": True, "result": {"path": "x.png"}, "warnings": []}


def test_success_with_warnings():
    w = warn(WarningCode.AUTO_DOWNSAMPLED, "downsampled", {"factor": 2})
    env = success({"k": 1}, warnings=[w])
    assert env["ok"] is True
    assert env["warnings"][0]["code"] == "auto_downsampled"
    assert env["warnings"][0]["context"]["factor"] == 2


def test_error_shape():
    env = error(ErrorCode.INVALID_SPEC, "missing values", context={"field": "values"})
    assert env == {
        "ok": False,
        "error": {"code": "invalid_spec",
                  "message": "missing values",
                  "context": {"field": "values"}},
    }


def test_ambiguous_shape():
    env = ambiguous(
        subcode=AmbiguitySubcode.CARTOPY_MISSING,
        message="install cartopy",
        candidates=[{"param": "install", "value": "uv pip install cartopy"}],
        retry_with_param=None,
        context={"hint": "use conda-forge"},
    )
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "cartopy_missing"
    assert env["error"]["candidates"][0]["param"] == "install"
```

- [ ] **Step 2: Run to verify failure**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_envelope.py -v
```

Expected: `ModuleNotFoundError: No module named 'src.mcp.plot_renderer.envelope'`.

- [ ] **Step 3: Implement `envelope.py`**

```python
# src/mcp/plot_renderer/envelope.py
"""⤴ format-agnostic — eligible for _core/ lift.

Locked cross-MCP envelope shape. Copied from cycle-1's envelope.py.
Keep these schemas in sync if either side changes.
"""
from __future__ import annotations

from typing import Any


class ErrorCode:
    INVALID_SPEC                  = "invalid_spec"
    OUTPUT_PATH_INVALID           = "output_path_invalid"
    OUTPUT_DIR_UNWRITABLE         = "output_dir_unwritable"
    SLICE_FILE_UNREADABLE         = "slice_file_unreadable"
    INTERNAL_RENDER_ERROR         = "internal_render_error"
    UNSUPPORTED_FORMAT            = "unsupported_format"
    FORMAT_EXTENSION_MISMATCH     = "format_extension_mismatch"
    INVALID_DPI                   = "invalid_dpi"
    TRENDLINE_DEPENDENCY_MISSING  = "trendline_dependency_missing"
    UNKNOWN_TOOL                  = "unknown_tool"


class AmbiguitySubcode:
    CARTOPY_MISSING       = "cartopy_missing"
    UNKNOWN_COLORMAP      = "unknown_colormap"
    UNKNOWN_PROJECTION    = "unknown_projection"
    EMPTY_SLICE           = "empty_slice"
    ALL_NAN               = "all_nan"


class WarningCode:
    AUTO_DOWNSAMPLED              = "auto_downsampled"
    CONSTANT_FIELD                = "constant_field"
    HIGH_NAN_FRACTION             = "high_nan_fraction"
    LON_SHIFT_APPLIED             = "lon_shift_applied"
    STYLE_TEMPLATE_PARTIAL        = "style_template_partially_applied"
    VCENTER_OUTSIDE_DATA_RANGE    = "vcenter_outside_data_range"
    COLOR_CYCLE_EXCEEDED          = "color_cycle_exceeded"
    PERCENTILE_CLIP_APPLIED       = "percentile_clip_applied"


def success(result: dict[str, Any], *,
            warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"ok": True, "result": result, "warnings": warnings or []}


def error(code: str, message: str, *,
          context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False,
            "error": {"code": code, "message": message,
                      "context": context or {}}}


def ambiguous(*, subcode: str, message: str,
              candidates: list[dict[str, Any]],
              retry_with_param: str | None = None,
              context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"ok": False,
            "error": {"code": "ambiguous",
                      "subcode": subcode,
                      "message": message,
                      "candidates": candidates,
                      "retry_with_param": retry_with_param,
                      "context": context or {}}}


def warn(code: str, message: str,
         context: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"code": code, "message": message, "context": context or {}}
```

- [ ] **Step 4: Run tests, verify green**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_envelope.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/envelope.py tests/mcp/plot_renderer/unit/test_envelope.py
git commit -m "cycle-2 task 2: envelope helpers + error/ambiguity/warning constants"
```

---

### Task 3: Library defaults

**Files:**
- Create: `src/mcp/plot_renderer/defaults.py`
- Create: `tests/mcp/plot_renderer/unit/test_defaults.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_defaults.py
from src.mcp.plot_renderer.defaults import LIBRARY_DEFAULTS


def test_library_defaults_shape():
    # Required fields present per spec §4.3
    required = {
        "colormap", "projection", "colorbar_position", "gridlines",
        "font_scale", "aspect", "dpi", "format", "downsample", "log_scale",
    }
    assert required.issubset(LIBRARY_DEFAULTS.keys())


def test_library_defaults_values():
    assert LIBRARY_DEFAULTS["colormap"] == "viridis"
    assert LIBRARY_DEFAULTS["projection"] == "PlateCarree"
    assert LIBRARY_DEFAULTS["dpi"] == 150
    assert LIBRARY_DEFAULTS["format"] == "png"
    assert LIBRARY_DEFAULTS["downsample"] is True


def test_library_defaults_immutable():
    # Defending against accidental mutation in code under test
    import copy
    snapshot = copy.deepcopy(LIBRARY_DEFAULTS)
    LIBRARY_DEFAULTS["colormap"] = "tab10"
    try:
        assert LIBRARY_DEFAULTS != snapshot   # mutation took effect
    finally:
        LIBRARY_DEFAULTS["colormap"] = snapshot["colormap"]
```

- [ ] **Step 2: Run, verify failure**

Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `defaults.py`**

```python
# src/mcp/plot_renderer/defaults.py
"""⤴ format-agnostic — eligible for _core/ lift.

Library-level safe defaults. Domain knowledge (anomaly → RdBu_r etc.)
lives in cycle-3 skills, not here.
"""
from __future__ import annotations

LIBRARY_DEFAULTS: dict[str, object] = {
    "colormap":          "viridis",
    "projection":        "PlateCarree",
    "colorbar_position": "right",
    "gridlines":         "light",
    "font_scale":        1.0,
    "aspect":            "auto",
    "dpi":               150,
    "format":            "png",
    "downsample":        True,
    "log_scale":         False,    # render_profile may override to True
}
```

- [ ] **Step 4: Run, verify green**

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/defaults.py tests/mcp/plot_renderer/unit/test_defaults.py
git commit -m "cycle-2 task 3: LIBRARY_DEFAULTS dict"
```

---

### Task 4: Colormap registry

**Files:**
- Create: `src/mcp/plot_renderer/colormap_registry.py`
- Create: `tests/mcp/plot_renderer/unit/test_colormap_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_colormap_registry.py
import pytest

from src.mcp.plot_renderer.colormap_registry import (
    is_known_cmap, validate_cmap_name, UnknownColormapError,
)


def test_known_cmap_returns_true():
    assert is_known_cmap("viridis") is True
    assert is_known_cmap("RdBu_r") is True
    assert is_known_cmap("tab10") is True


def test_unknown_cmap_returns_false():
    assert is_known_cmap("definitely_not_a_real_cmap") is False
    assert is_known_cmap("Rainbow") is False  # capital R; matplotlib has 'rainbow'


def test_validate_passes_for_known():
    validate_cmap_name("viridis")  # no exception


def test_validate_raises_unknown():
    with pytest.raises(UnknownColormapError) as exc:
        validate_cmap_name("not_a_cmap")
    assert "not_a_cmap" in str(exc.value)
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `colormap_registry.py`**

```python
# src/mcp/plot_renderer/colormap_registry.py
"""⤴ format-agnostic — eligible for _core/ lift.

Lazy-loaded matplotlib colormap registry wrapper. Centralizes cmap
validation so style.py / safety.py / tools/* can check without each
importing matplotlib.cm directly.
"""
from __future__ import annotations


class UnknownColormapError(ValueError):
    pass


def _registry() -> set[str]:
    # Lazy import: matplotlib loads on first call only.
    import matplotlib as mpl
    return set(mpl.colormaps)


def is_known_cmap(name: str) -> bool:
    return name in _registry()


def validate_cmap_name(name: str) -> None:
    if not is_known_cmap(name):
        raise UnknownColormapError(
            f"colormap {name!r} is not in matplotlib's registry")
```

- [ ] **Step 4: Run, verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/colormap_registry.py \
        tests/mcp/plot_renderer/unit/test_colormap_registry.py
git commit -m "cycle-2 task 4: colormap_registry with lazy matplotlib import"
```

---

### Task 5: Phase-1 lint and typecheck gate

**Files:** none new; just verification.

- [ ] **Step 1: Run ruff on cycle-2 sources**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer
```

Expected: no violations.

- [ ] **Step 2: Run mypy on cycle-2 sources**

```bash
.venv/bin/mypy src/mcp/plot_renderer
```

Expected: `Success: no issues found in N source files`.

- [ ] **Step 3: Run the full plot_renderer test suite**

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

Expected: all tests pass (envelope + defaults + colormap_registry).

- [ ] **Step 4: No commit needed if no changes — gate only.**

If any fix was required to pass lint/mypy, commit it:

```bash
git add -A
git commit -m "cycle-2 phase-1 gate: lint + typecheck clean"
```

---

## Phase 2: Data adapter + slice loader

Phase 2 normalizes the two input forms (inline + slice_ref) into a
consistent typed shape (numpy values + xarray DataArray-like coords)
that all downstream modules consume. The slice loader is the only
format-specific module; it carries `__format_specific__ = True` for
the seam test.

### Task 6: SliceLoader Protocol

**Files:**
- Create: `src/mcp/plot_renderer/protocols.py`
- Create: `tests/mcp/plot_renderer/unit/test_protocols.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_protocols.py
from typing import Any

from src.mcp.plot_renderer.protocols import SliceLoader


class _DummyLoader:
    name = "dummy"
    supported_formats = {"netcdf"}

    def load(self, slice_ref: dict[str, Any]):
        return None


def test_dummy_loader_satisfies_protocol():
    assert isinstance(_DummyLoader(), SliceLoader)


def test_loader_missing_attr_fails_protocol():
    class Bad:
        pass
    assert not isinstance(Bad(), SliceLoader)
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `protocols.py`**

```python
# src/mcp/plot_renderer/protocols.py
"""⤴ format-agnostic — eligible for _core/ lift.

Holds format-agnostic Protocol definitions sitting at the seam between
cycle-2's renderer and a future _core/ package. The concrete NetCDF
SliceLoader lives in slice_loader.py (format-specific); this module
names the interface so format-agnostic callers can depend on it.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import xarray as xr


@runtime_checkable
class SliceLoader(Protocol):
    name: str
    supported_formats: set[str]

    def load(self, slice_ref: dict[str, Any]) -> xr.DataArray: ...
```

- [ ] **Step 4: Run, verify green**

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/protocols.py \
        tests/mcp/plot_renderer/unit/test_protocols.py
git commit -m "cycle-2 task 6: SliceLoader Protocol"
```

---

### Task 7: Inline-form adapter

**Files:**
- Create: `src/mcp/plot_renderer/adapter.py` (initial; grows in Task 9)
- Create: `tests/mcp/plot_renderer/unit/test_adapter_inline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_adapter_inline.py
import math

import numpy as np

from src.mcp.plot_renderer.adapter import (
    InvalidSpecError, normalize_2d, normalize_1d_series,
)


def test_inline_2d_basic():
    spec = {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [10.0, 20.0],
        "units": "K",
    }
    arr, coords, meta = normalize_2d(spec)
    assert arr.shape == (2, 2)
    assert arr.dtype.kind == "f"
    assert list(coords["lat"]) == [0.0, 1.0]
    assert list(coords["lon"]) == [10.0, 20.0]
    assert meta["units"] == "K"


def test_inline_2d_decodes_nan_string():
    spec = {
        "values": [[1.0, "NaN"], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [10.0, 20.0],
    }
    arr, _, _ = normalize_2d(spec)
    assert math.isnan(arr[0, 1])
    assert arr[1, 0] == 3.0


def test_inline_2d_missing_lat_errors():
    spec = {"values": [[1.0]], "lon": [0.0]}
    try:
        normalize_2d(spec)
    except InvalidSpecError as e:
        assert "lat" in str(e)
        return
    raise AssertionError("expected InvalidSpecError")


def test_inline_1d_series_single_sugar():
    spec = {"values": [1.0, 2.0, 3.0],
            "time": ["2024-01", "2024-02", "2024-03"],
            "label": "demo"}
    series = normalize_1d_series(spec, axis_name="time")
    assert len(series) == 1
    assert series[0]["label"] == "demo"
    assert list(series[0]["values"]) == [1.0, 2.0, 3.0]
    # ISO strings parsed to datetime64
    assert np.issubdtype(series[0]["axis"].dtype, np.datetime64)


def test_inline_1d_series_multi():
    spec = {"series": [
        {"values": [1.0], "time": ["2024-01"], "label": "A"},
        {"values": [2.0], "time": ["2024-01"], "label": "B"},
    ]}
    series = normalize_1d_series(spec, axis_name="time")
    assert [s["label"] for s in series] == ["A", "B"]


def test_inline_1d_series_both_set_errors():
    spec = {"values": [1.0], "time": ["2024-01"],
            "series": [{"values": [2.0], "time": ["2024-01"]}]}
    try:
        normalize_1d_series(spec, axis_name="time")
    except InvalidSpecError as e:
        assert "series_and_sugar_both_set" in str(e)
        return
    raise AssertionError("expected InvalidSpecError")


def test_inline_1d_series_profile_axis():
    spec = {"values": [288.0, 250.0],
            "vertical": [1000.0, 500.0],
            "vertical_units": "hPa", "label": "demo"}
    series = normalize_1d_series(spec, axis_name="vertical")
    assert len(series) == 1
    assert list(series[0]["axis"]) == [1000.0, 500.0]
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `adapter.py` (inline-only for now)**

```python
# src/mcp/plot_renderer/adapter.py
"""⤴ format-agnostic — eligible for _core/ lift.

Spec → typed numpy arrays. Decodes the inline JSON form (NaN strings,
nested lists, ISO time strings) and (in Task 9) dispatches the
slice_ref form to slice_loader. Renderer-side modules consume only
the outputs of this module — they never see the raw spec dict.
"""
from __future__ import annotations

from typing import Any

import numpy as np


class InvalidSpecError(ValueError):
    pass


def _decode_nans(values: Any) -> np.ndarray:
    """Convert nested lists with possible string 'NaN' into a float array."""
    arr = np.asarray(values, dtype=object)
    flat = arr.reshape(-1)
    out = np.empty(flat.shape, dtype="float64")
    for i, v in enumerate(flat):
        if isinstance(v, str) and v == "NaN":
            out[i] = np.nan
        else:
            out[i] = float(v)
    return out.reshape(arr.shape)


def _decode_axis(values: Any, axis_name: str) -> np.ndarray:
    """Decode an axis (lat/lon = float, time = datetime64, vertical = float)."""
    if axis_name == "time":
        # Strings → datetime64; pass-throughs already datetime stay
        return np.array(values, dtype="datetime64[ns]")
    return np.asarray(values, dtype="float64")


def normalize_2d(spec: dict[str, Any]) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Normalize a render_map inline spec.

    Returns (values, coords, meta). values shape is (n_lat, n_lon).
    """
    if "values" not in spec:
        raise InvalidSpecError("missing required field: values")
    if "lat" not in spec:
        raise InvalidSpecError("missing required field: lat")
    if "lon" not in spec:
        raise InvalidSpecError("missing required field: lon")
    values = _decode_nans(spec["values"])
    lat = _decode_axis(spec["lat"], "lat")
    lon = _decode_axis(spec["lon"], "lon")
    if values.ndim != 2:
        raise InvalidSpecError(
            f"render_map values must be 2D, got shape {values.shape}")
    meta = {k: spec[k] for k in ("units", "long_name", "standard_name",
                                  "variable", "lon_convention")
            if k in spec}
    return values, {"lat": lat, "lon": lon}, meta


def normalize_1d_series(
    spec: dict[str, Any], *, axis_name: str,
) -> list[dict[str, Any]]:
    """Normalize render_timeseries / render_profile spec into a series list.

    axis_name is "time" for timeseries, "vertical" for profile.
    """
    has_series = "series" in spec and spec["series"] is not None
    has_sugar = "values" in spec and axis_name in spec
    if has_series and has_sugar:
        raise InvalidSpecError(
            "series_and_sugar_both_set: supply either `series` or "
            f"`values+{axis_name}`, not both")
    if not has_series and not has_sugar:
        raise InvalidSpecError(
            f"missing required data: provide `series` or `values+{axis_name}`")

    raw_series: list[dict[str, Any]]
    if has_series:
        raw_series = list(spec["series"])
    else:
        raw_series = [{"values": spec["values"], axis_name: spec[axis_name],
                       "label": spec.get("label")}]

    out: list[dict[str, Any]] = []
    for i, s in enumerate(raw_series):
        if "values" not in s:
            raise InvalidSpecError(f"series[{i}] missing values")
        if axis_name not in s:
            raise InvalidSpecError(f"series[{i}] missing {axis_name}")
        values = _decode_nans(s["values"])
        axis = _decode_axis(s[axis_name], axis_name)
        if values.ndim != 1:
            raise InvalidSpecError(
                f"series[{i}] values must be 1D, got shape {values.shape}")
        if axis.shape != values.shape:
            raise InvalidSpecError(
                f"series[{i}] {axis_name} length {axis.shape[0]} != values "
                f"length {values.shape[0]}")
        out.append({
            "values": values,
            "axis":   axis,
            "label":  s.get("label") or f"series_{i}",
            "color":  s.get("color"),
        })
    return out
```

- [ ] **Step 4: Run, verify green**

Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/adapter.py \
        tests/mcp/plot_renderer/unit/test_adapter_inline.py
git commit -m "cycle-2 task 7: inline-form adapter (2D + 1D series)"
```

---

### Task 8: NetCDF slice_loader

**Files:**
- Create: `src/mcp/plot_renderer/slice_loader.py`
- Create: `tests/mcp/plot_renderer/unit/test_slice_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_slice_loader.py
import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.slice_loader import (
    NetCDFSliceLoader, SliceFileUnreadable,
)


@pytest.fixture
def slice_file(tmp_path):
    p = tmp_path / "slice.nc"
    ds = xr.Dataset(
        {"v": (("lat", "lon"), np.arange(6, dtype="f4").reshape(2, 3),
               {"units": "K", "long_name": "demo"})},
        coords={"lat": [0.0, 1.0], "lon": [0.0, 1.0, 2.0]},
        attrs={"Conventions": "CF-1.7"},
    )
    ds.to_netcdf(p, engine="h5netcdf")
    return p


def test_load_returns_named_variable(slice_file):
    loader = NetCDFSliceLoader()
    da = loader.load({"path": str(slice_file), "format": "netcdf",
                      "variable": "v"})
    assert da.shape == (2, 3)
    assert da.attrs["units"] == "K"


def test_load_missing_variable_raises(slice_file):
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable) as exc:
        loader.load({"path": str(slice_file), "format": "netcdf",
                     "variable": "does_not_exist"})
    assert "does_not_exist" in str(exc.value)


def test_load_missing_path_raises():
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable):
        loader.load({"path": "/does/not/exist.nc", "format": "netcdf",
                     "variable": "v"})


def test_load_unknown_format_raises():
    loader = NetCDFSliceLoader()
    with pytest.raises(SliceFileUnreadable) as exc:
        loader.load({"path": "x", "format": "zarr", "variable": "v"})
    assert "format" in str(exc.value).lower()


def test_format_specific_marker():
    from src.mcp.plot_renderer import slice_loader as mod
    assert getattr(mod, "__format_specific__", False) is True
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `slice_loader.py`**

```python
# src/mcp/plot_renderer/slice_loader.py
"""FORMAT-SPECIFIC: NetCDF SliceLoader.

This is the only file in cycle-2 that imports a NetCDF library. The
seam test reads __format_specific__ to skip it during the no-format
import audit.
"""
from __future__ import annotations

from typing import Any

import xarray as xr

__format_specific__ = True


class SliceFileUnreadable(Exception):
    pass


class NetCDFSliceLoader:
    name = "netcdf"
    supported_formats = {"netcdf"}

    def load(self, slice_ref: dict[str, Any]) -> xr.DataArray:
        fmt = slice_ref.get("format")
        if fmt not in self.supported_formats:
            raise SliceFileUnreadable(
                f"unsupported slice format: {fmt!r}; "
                f"this loader handles {sorted(self.supported_formats)}")
        path = slice_ref.get("path")
        var = slice_ref.get("variable")
        if not path:
            raise SliceFileUnreadable("slice_ref.path is missing or empty")
        if not var:
            raise SliceFileUnreadable("slice_ref.variable is missing or empty")
        try:
            ds = xr.open_dataset(path, engine="h5netcdf",
                                 decode_times=True, chunks="auto")
        except FileNotFoundError as e:
            raise SliceFileUnreadable(f"file not found: {path}") from e
        except (OSError, ValueError) as e:
            raise SliceFileUnreadable(
                f"cannot open {path}: {type(e).__name__}: {e}") from e
        if var not in ds.data_vars:
            raise SliceFileUnreadable(
                f"variable {var!r} not found in {path}; "
                f"available: {sorted(ds.data_vars)}")
        return ds[var]
```

- [ ] **Step 4: Run, verify green**

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/slice_loader.py \
        tests/mcp/plot_renderer/unit/test_slice_loader.py
git commit -m "cycle-2 task 8: NetCDF slice_loader (format-specific)"
```

---

### Task 9: slice_ref adapter dispatch

**Files:**
- Modify: `src/mcp/plot_renderer/adapter.py` (add slice_ref handling)
- Create: `tests/mcp/plot_renderer/unit/test_adapter_slice_ref.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_adapter_slice_ref.py
import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.adapter import (
    InvalidSpecError, normalize_2d_any_form,
)


@pytest.fixture
def slice_file(tmp_path):
    p = tmp_path / "slice.nc"
    lat = np.array([0.0, 1.0])
    lon = np.array([0.0, 1.0, 2.0])
    values = np.arange(6, dtype="f4").reshape(2, 3)
    ds = xr.Dataset(
        {"v": (("lat", "lon"), values, {"units": "K"})},
        coords={"lat": lat, "lon": lon},
    )
    ds.to_netcdf(p, engine="h5netcdf")
    return p


def test_normalize_inline_form(small_2d_dataset):
    spec = {
        "values": small_2d_dataset["v"].values.tolist(),
        "lat": small_2d_dataset["lat"].values.tolist(),
        "lon": small_2d_dataset["lon"].values.tolist(),
        "units": "K",
    }
    values, coords, meta = normalize_2d_any_form(spec)
    assert values.shape == (7, 13)
    assert meta["units"] == "K"


def test_normalize_slice_ref_form(slice_file):
    spec = {"slice_ref": {"path": str(slice_file), "format": "netcdf",
                          "variable": "v"}}
    values, coords, meta = normalize_2d_any_form(spec)
    assert values.shape == (2, 3)
    assert "lat" in coords and "lon" in coords
    assert meta["units"] == "K"


def test_both_forms_set_errors(slice_file):
    spec = {"values": [[1.0]], "lat": [0.0], "lon": [0.0],
            "slice_ref": {"path": str(slice_file), "format": "netcdf",
                          "variable": "v"}}
    with pytest.raises(InvalidSpecError):
        normalize_2d_any_form(spec)


def test_neither_form_errors():
    with pytest.raises(InvalidSpecError):
        normalize_2d_any_form({})
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append slice_ref dispatch to `adapter.py`**

Add after the existing `normalize_1d_series`:

```python
def normalize_2d_any_form(
    spec: dict[str, Any],
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Dispatch on inline vs slice_ref form for render_map specs."""
    has_inline = "values" in spec
    has_slice_ref = spec.get("slice_ref") is not None
    if has_inline and has_slice_ref:
        raise InvalidSpecError(
            "supply either inline values or slice_ref, not both")
    if not has_inline and not has_slice_ref:
        raise InvalidSpecError("missing data: provide values+lat+lon or slice_ref")
    if has_inline:
        return normalize_2d(spec)
    # slice_ref path
    from src.mcp.plot_renderer.slice_loader import (
        NetCDFSliceLoader, SliceFileUnreadable,
    )
    try:
        da = NetCDFSliceLoader().load(spec["slice_ref"])
    except SliceFileUnreadable as e:
        raise InvalidSpecError(f"slice_ref unreadable: {e}") from e
    # Squeeze leading singleton dims (e.g., time=1)
    da = da.squeeze(drop=True)
    if da.ndim != 2:
        raise InvalidSpecError(
            f"slice_ref variable must reduce to 2D for render_map; got {da.ndim}D")
    # Try to find lat/lon coord names; fall back to dim names.
    dim_lat, dim_lon = da.dims
    coords = {
        "lat": np.asarray(da[dim_lat].values, dtype="float64"),
        "lon": np.asarray(da[dim_lon].values, dtype="float64"),
    }
    values = np.asarray(da.values, dtype="float64")
    meta: dict[str, Any] = {
        k: da.attrs[k] for k in ("units", "long_name", "standard_name")
        if k in da.attrs
    }
    if "variable" in spec.get("slice_ref", {}):
        meta["variable"] = spec["slice_ref"]["variable"]
    if spec.get("lon_convention") is not None:
        meta["lon_convention"] = spec["lon_convention"]
    return values, coords, meta
```

- [ ] **Step 4: Run, verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/adapter.py \
        tests/mcp/plot_renderer/unit/test_adapter_slice_ref.py
git commit -m "cycle-2 task 9: adapter dispatch — inline vs slice_ref"
```

---

### Task 10: Phase-2 lint and typecheck gate

- [ ] **Step 1: Run ruff**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer
```

- [ ] **Step 2: Run mypy**

```bash
.venv/bin/mypy src/mcp/plot_renderer
```

- [ ] **Step 3: Run plot_renderer tests**

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

Expected: all passing (envelope + defaults + colormap_registry + protocols + adapter + slice_loader).

- [ ] **Step 4: Commit if any fixes**

```bash
git add -A
git commit -m "cycle-2 phase-2 gate: lint + typecheck clean"
```

---

## Phase 3: Safety pass

The safety pass owns the robustness behaviors from spec §7:
auto-downsample, NaN handling (incl. all-NaN ambiguity), longitude
shift, constant-field warning, and percentile clipping for extreme
outliers. It runs AFTER style application but BEFORE rendering.

### Task 11: Auto-downsample (2D and 1D)

**Files:**
- Create: `src/mcp/plot_renderer/safety.py` (initial; grows in tasks 12-14)
- Create: `tests/mcp/plot_renderer/unit/test_safety_downsample.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_safety_downsample.py
import numpy as np

from src.mcp.plot_renderer.safety import (
    DOWNSAMPLE_2D_THRESHOLD, DOWNSAMPLE_1D_THRESHOLD,
    auto_downsample_2d, auto_downsample_1d,
)


def test_2d_below_threshold_unchanged():
    arr = np.zeros((100, 100), dtype="f4")
    coords = {"lat": np.arange(100, dtype="f8"),
              "lon": np.arange(100, dtype="f8")}
    out, out_coords, action = auto_downsample_2d(arr, coords, enabled=True)
    assert out.shape == (100, 100)
    assert action is None


def test_2d_above_threshold_downsamples():
    # 4M cells exactly at threshold → no action; one above → action.
    n = 2049
    arr = np.zeros((n, n), dtype="f4")
    coords = {"lat": np.arange(n, dtype="f8"),
              "lon": np.arange(n, dtype="f8")}
    out, out_coords, action = auto_downsample_2d(arr, coords, enabled=True)
    assert out.shape[0] * out.shape[1] <= DOWNSAMPLE_2D_THRESHOLD
    assert action is not None
    assert action["from_shape"] == (n, n)
    assert action["to_shape"] == out.shape
    assert action["factor"]["lat"] >= 2
    assert out_coords["lat"].shape[0] == out.shape[0]


def test_2d_disabled_returns_full_array():
    n = 2049
    arr = np.zeros((n, n), dtype="f4")
    coords = {"lat": np.arange(n, dtype="f8"),
              "lon": np.arange(n, dtype="f8")}
    out, _, action = auto_downsample_2d(arr, coords, enabled=False)
    assert out.shape == (n, n)
    assert action is None


def test_1d_below_threshold_unchanged():
    arr = np.zeros(50_000, dtype="f4")
    axis = np.arange(50_000)
    out, out_axis, action = auto_downsample_1d(arr, axis, enabled=True)
    assert out.shape[0] == 50_000
    assert action is None


def test_1d_above_threshold_decimates():
    n = DOWNSAMPLE_1D_THRESHOLD + 1
    arr = np.arange(n, dtype="f4")
    axis = np.arange(n)
    out, out_axis, action = auto_downsample_1d(arr, axis, enabled=True)
    assert out.shape[0] <= DOWNSAMPLE_1D_THRESHOLD
    assert action is not None
    assert action["from_shape"] == (n,)


def test_2d_disabled_with_huge_returns_full():
    arr = np.zeros((3000, 3000), dtype="f4")
    coords = {"lat": np.arange(3000, dtype="f8"),
              "lon": np.arange(3000, dtype="f8")}
    out, _, action = auto_downsample_2d(arr, coords, enabled=False)
    assert action is None
    assert out.shape == (3000, 3000)
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `safety.py` (downsample-only for now)**

```python
# src/mcp/plot_renderer/safety.py
"""⤴ format-agnostic — eligible for _core/ lift.

Robustness behaviors for the renderer (spec §7). The safety pass runs
on already-normalized numpy arrays AFTER style resolution and BEFORE
the matplotlib drawing call.
"""
from __future__ import annotations

from math import ceil
from typing import Any

import numpy as np


DOWNSAMPLE_2D_THRESHOLD = 4_000_000   # cells (e.g. 2048 × 2048)
DOWNSAMPLE_1D_THRESHOLD = 100_000     # points


def _coarsen_factor(n: int, target: int) -> int:
    """Smallest k >= 1 such that n // k <= target."""
    if n <= target:
        return 1
    return int(ceil(n / target))


def auto_downsample_2d(
    values: np.ndarray, coords: dict[str, np.ndarray], *, enabled: bool,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any] | None]:
    """Downsample 2D array via per-axis coarsening if total cells exceed
    threshold and `enabled` is True. Returns (values, coords, action) where
    action is None when no downsample happened.
    """
    if not enabled:
        return values, coords, None
    n_lat, n_lon = values.shape
    if n_lat * n_lon <= DOWNSAMPLE_2D_THRESHOLD:
        return values, coords, None
    # Compute per-axis factor proportional to a sqrt-balance toward the cap.
    target_each = int(DOWNSAMPLE_2D_THRESHOLD ** 0.5)
    k_lat = _coarsen_factor(n_lat, target_each)
    k_lon = _coarsen_factor(n_lon, target_each)
    # Trim to multiples of the factor so reshape is clean.
    n_lat_trim = (n_lat // k_lat) * k_lat
    n_lon_trim = (n_lon // k_lon) * k_lon
    arr = values[:n_lat_trim, :n_lon_trim].reshape(
        n_lat_trim // k_lat, k_lat, n_lon_trim // k_lon, k_lon,
    ).mean(axis=(1, 3))
    new_coords = {
        "lat": coords["lat"][:n_lat_trim].reshape(-1, k_lat).mean(axis=1),
        "lon": coords["lon"][:n_lon_trim].reshape(-1, k_lon).mean(axis=1),
    }
    return arr, new_coords, {
        "from_shape": (n_lat, n_lon),
        "to_shape": arr.shape,
        "factor": {"lat": k_lat, "lon": k_lon},
    }


def auto_downsample_1d(
    values: np.ndarray, axis: np.ndarray, *, enabled: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any] | None]:
    """Stride-decimate a 1D array if length exceeds threshold."""
    if not enabled:
        return values, axis, None
    n = values.shape[0]
    if n <= DOWNSAMPLE_1D_THRESHOLD:
        return values, axis, None
    k = _coarsen_factor(n, DOWNSAMPLE_1D_THRESHOLD)
    return (values[::k], axis[::k],
            {"from_shape": (n,), "to_shape": (values[::k].shape[0],),
             "factor": {"axis": k}})
```

- [ ] **Step 4: Run, verify green**

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/safety.py \
        tests/mcp/plot_renderer/unit/test_safety_downsample.py
git commit -m "cycle-2 task 11: safety auto_downsample 2d + 1d"
```

---

### Task 12: NaN handling and all-NaN ambiguity

**Files:**
- Modify: `src/mcp/plot_renderer/safety.py`
- Create: `tests/mcp/plot_renderer/unit/test_safety_nan.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_safety_nan.py
import numpy as np

from src.mcp.plot_renderer.safety import nan_assessment


def test_no_nans():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.0
    assert assess["all_nan"] is False
    assert assess["high_nan_fraction"] is False


def test_all_nan_flag():
    arr = np.full((3, 3), np.nan)
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 1.0
    assert assess["all_nan"] is True
    assert assess["high_nan_fraction"] is True


def test_high_nan_threshold_50pct():
    arr = np.array([[np.nan, np.nan, 1.0, 2.0]])  # 50%
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.5
    # Strictly > 0.5 trips the warning; exactly 0.5 does not.
    assert assess["high_nan_fraction"] is False


def test_high_nan_above_50():
    arr = np.array([[np.nan, np.nan, np.nan, 1.0]])  # 75%
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.75
    assert assess["high_nan_fraction"] is True


def test_nan_assessment_on_1d():
    arr = np.array([np.nan, 1.0, 2.0, np.nan])
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.5
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `safety.py`**

```python
def nan_assessment(values: np.ndarray) -> dict[str, Any]:
    """Compute NaN statistics. Threshold for `high_nan_fraction` is > 0.5."""
    total = values.size
    if total == 0:
        return {"nan_fraction": 0.0, "all_nan": False,
                "high_nan_fraction": False}
    n_nan = int(np.isnan(values).sum())
    frac = n_nan / total
    return {
        "nan_fraction": frac,
        "all_nan": (n_nan == total),
        "high_nan_fraction": (frac > 0.5),
    }
```

- [ ] **Step 4: Run, verify green**

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/safety.py \
        tests/mcp/plot_renderer/unit/test_safety_nan.py
git commit -m "cycle-2 task 12: safety nan_assessment helper"
```

---

### Task 13: Longitude shift (`render_map` only)

**Files:**
- Modify: `src/mcp/plot_renderer/safety.py`
- Create: `tests/mcp/plot_renderer/unit/test_safety_lon_shift.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_safety_lon_shift.py
import numpy as np

from src.mcp.plot_renderer.safety import maybe_lon_shift


def test_no_convention_no_shift():
    values = np.arange(12).reshape(3, 4).astype("f4")
    lon = np.array([10.0, 20.0, 30.0, 40.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target=None)
    assert applied is False
    np.testing.assert_array_equal(out_v, values)
    np.testing.assert_array_equal(out_lon, lon)


def test_target_already_matches_no_shift():
    values = np.arange(8).reshape(2, 4).astype("f4")
    lon = np.array([-90.0, -45.0, 0.0, 45.0])  # already in -180..180
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="-180..180")
    assert applied is False


def test_shift_360_to_signed():
    # data is on 0..360 (e.g. lon=[180,270,0,90]); want -180..180
    values = np.array([[1.0, 2.0, 3.0, 4.0]])
    lon = np.array([180.0, 270.0, 0.0, 90.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="-180..180")
    assert applied is True
    assert out_lon.min() >= -180.0 and out_lon.max() <= 180.0
    # values must remain associated with their original lon labels:
    # original (180, 1.0), (270, 2.0), (0, 3.0), (90, 4.0)
    # post-shift: (-180, 1.0), (-90, 2.0), (0, 3.0), (90, 4.0) sorted ascending
    pairs = sorted(zip(out_lon.tolist(), out_v[0].tolist()))
    assert pairs == [(-180.0, 1.0), (-90.0, 2.0), (0.0, 3.0), (90.0, 4.0)]


def test_shift_signed_to_360():
    values = np.array([[1.0, 2.0, 3.0, 4.0]])
    lon = np.array([-90.0, 0.0, 90.0, 180.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="0..360")
    assert applied is True
    pairs = sorted(zip(out_lon.tolist(), out_v[0].tolist()))
    # -90→270, 0→0, 90→90, 180→180
    assert pairs == [(0.0, 2.0), (90.0, 3.0), (180.0, 4.0), (270.0, 1.0)]
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `safety.py`**

```python
def maybe_lon_shift(
    values: np.ndarray, lon: np.ndarray, *, target: str | None,
) -> tuple[np.ndarray, np.ndarray, bool]:
    """Shift longitude convention if `target` is set and current data
    doesn't satisfy it. Returns (values, lon, applied).

    target ∈ {None, "-180..180", "0..360"}.
    """
    if target is None:
        return values, lon, False
    if target == "-180..180":
        if lon.min() >= -180.0 and lon.max() <= 180.0:
            return values, lon, False
        new_lon = ((lon + 180.0) % 360.0) - 180.0
    elif target == "0..360":
        if lon.min() >= 0.0 and lon.max() <= 360.0:
            return values, lon, False
        new_lon = lon % 360.0
    else:
        # Unknown target: pass through; caller may have validated already.
        return values, lon, False
    order = np.argsort(new_lon, kind="stable")
    sorted_lon = new_lon[order]
    # Re-order along the lon axis (last axis for 2D values shape (lat, lon)).
    sorted_values = np.take(values, order, axis=-1)
    return sorted_values, sorted_lon, True
```

- [ ] **Step 4: Run, verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/safety.py \
        tests/mcp/plot_renderer/unit/test_safety_lon_shift.py
git commit -m "cycle-2 task 13: safety maybe_lon_shift"
```

---

### Task 14: Constant field detection + percentile clip + run() coordinator

**Files:**
- Modify: `src/mcp/plot_renderer/safety.py`
- Create: `tests/mcp/plot_renderer/unit/test_safety_constant.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_safety_constant.py
import numpy as np

from src.mcp.plot_renderer.safety import (
    is_constant_field, percentile_clip_if_extreme,
)


def test_constant_true():
    arr = np.full((3, 3), 7.0)
    is_const, value = is_constant_field(arr)
    assert is_const is True
    assert value == 7.0


def test_constant_false():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    is_const, value = is_constant_field(arr)
    assert is_const is False
    assert value is None


def test_constant_nan_only():
    arr = np.array([[np.nan, np.nan]])
    is_const, value = is_constant_field(arr)
    # All-NaN counts as constant (no variation); but "value" is None.
    assert is_const is True
    assert value is None


def test_clip_no_op_for_normal_range():
    arr = np.array([[0.0, 1.0, 2.0, 3.0, 4.0]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr)
    # Range only 4 orders or less of magnitude → no clip.
    assert applied is False
    assert vmin == 0.0
    assert vmax == 4.0


def test_clip_triggers_for_extreme_outliers():
    # Median ~1.0, one cell at -9e36 (the classic missing-value sentinel).
    arr = np.array([[1.0, 1.0, 1.0, 1.0, -9.0e36]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr)
    assert applied is True
    # Clip uses 2/98 percentiles; these are above -9e36 and below max.
    assert vmin > -9.0e36
    assert vmin <= vmax


def test_clip_skips_with_explicit_vmin_vmax():
    arr = np.array([[1.0, 1.0, 1.0, 1.0, -9.0e36]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr, vmin=0.0, vmax=2.0)
    assert applied is False
    assert vmin == 0.0
    assert vmax == 2.0
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `safety.py`**

```python
def is_constant_field(values: np.ndarray) -> tuple[bool, float | None]:
    """Return (True, value) if all non-NaN values are identical (or array
    is all-NaN, with value=None). Otherwise (False, None)."""
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return True, None
    if finite.min() == finite.max():
        return True, float(finite.min())
    return False, None


def percentile_clip_if_extreme(
    values: np.ndarray, *,
    vmin: float | None = None,
    vmax: float | None = None,
    clip_pct: tuple[float, float] | None = None,
    extreme_orders_of_magnitude: float = 6.0,
) -> tuple[float, float, bool]:
    """Decide vmin/vmax for the colormap.

    - If user/template supplied vmin and vmax, return them unchanged.
    - If clip_pct is supplied, apply it (always).
    - Otherwise, if data spans more than `extreme_orders_of_magnitude`,
      apply a [2, 98] percentile clip to suppress outliers.
    - Otherwise return (data_min, data_max).

    Returns (vmin, vmax, applied) where applied=True only when a
    percentile clip was actually applied.
    """
    if vmin is not None and vmax is not None:
        return float(vmin), float(vmax), False
    finite = values[np.isfinite(values)]
    if finite.size == 0:
        return float("nan"), float("nan"), False
    if clip_pct is not None:
        lo, hi = clip_pct
        v_lo = float(np.percentile(finite, lo))
        v_hi = float(np.percentile(finite, hi))
        return v_lo, v_hi, True
    data_min = float(finite.min())
    data_max = float(finite.max())
    abs_max = max(abs(data_min), abs(data_max))
    abs_min_nonzero = max(abs(data_min), abs(data_max), 1e-300)
    median_abs = float(np.median(np.abs(finite)))
    median_abs = max(median_abs, 1e-300)
    if abs_max / median_abs > 10 ** extreme_orders_of_magnitude:
        v_lo = float(np.percentile(finite, 2.0))
        v_hi = float(np.percentile(finite, 98.0))
        return v_lo, v_hi, True
    # Fallback: no clip, no smarts beyond user override
    _ = abs_min_nonzero  # keeps the linter quiet without affecting logic
    return data_min, data_max, False
```

- [ ] **Step 4: Run, verify green**

Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/safety.py \
        tests/mcp/plot_renderer/unit/test_safety_constant.py
git commit -m "cycle-2 task 14: safety is_constant_field + percentile_clip_if_extreme"
```

---

### Task 15: Phase-3 lint and typecheck gate

- [ ] **Step 1: Run ruff**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer
```

- [ ] **Step 2: Run mypy**

```bash
.venv/bin/mypy src/mcp/plot_renderer
```

- [ ] **Step 3: Run plot_renderer tests**

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

Expected: all unit tests pass.

- [ ] **Step 4: Commit if any fixes**

```bash
git add -A
git commit -m "cycle-2 phase-3 gate: lint + typecheck clean"
```

---

## Phase 4: Style template

Phase 4 implements the `style_template` schema (spec §8) — the
deterministic application of a user-supplied style hint dict onto a
working spec. Resolution order: explicit > template > library_default.

### Task 16: Mapping table for colormap-related fields

**Files:**
- Create: `src/mcp/plot_renderer/style.py` (initial; grows in tasks 17-18)
- Create: `tests/mcp/plot_renderer/unit/test_style_application.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_style_application.py
from src.mcp.plot_renderer.style import apply, _MAPPING


def test_colormap_name_direct():
    spec = {}
    template = {"colormap_name": "RdYlBu_r"}
    resolved, trace = apply(spec, template)
    assert resolved["colormap"] == "RdYlBu_r"
    assert "colormap_name" in trace["fields_applied"]


def test_colormap_kind_sequential():
    resolved, trace = apply({}, {"colormap_kind": "sequential"})
    assert resolved["colormap"] == "viridis"
    assert "colormap_kind" in trace["fields_applied"]


def test_colormap_kind_diverging_sets_vcenter():
    resolved, trace = apply({}, {"colormap_kind": "diverging"})
    assert resolved["colormap"] == "RdBu_r"
    assert resolved["vcenter"] == 0.0


def test_colormap_kind_categorical():
    resolved, _ = apply({}, {"colormap_kind": "categorical"})
    assert resolved["colormap"] == "tab10"


def test_explicit_colormap_beats_template():
    resolved, trace = apply(
        {"colormap": "magma"},
        {"colormap_kind": "diverging"},
    )
    assert resolved["colormap"] == "magma"
    assert any(f["field"] == "colormap_kind" and
               f["reason"] == "overridden_by_explicit_spec"
               for f in trace["fields_ignored"])


def test_colormap_name_takes_precedence_over_kind_in_template():
    resolved, _ = apply({}, {"colormap_name": "plasma",
                              "colormap_kind": "sequential"})
    assert resolved["colormap"] == "plasma"


def test_clip_pct_passthrough():
    resolved, _ = apply({}, {"clip_pct": [5.0, 95.0]})
    assert resolved["clip_pct"] == [5.0, 95.0]


def test_vcenter_passthrough():
    resolved, _ = apply({}, {"vcenter": 0.5})
    assert resolved["vcenter"] == 0.5


def test_mapping_table_has_all_template_keys():
    expected = {
        "colormap_name", "colormap_kind", "vcenter", "clip_pct",
    }
    for k in expected:
        assert k in _MAPPING
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `style.py` (colormap fields only)**

```python
# src/mcp/plot_renderer/style.py
"""⤴ format-agnostic — eligible for _core/ lift.

Deterministic application of a `style_template` dict onto a working
spec. See spec §8.

Precedence rule: explicit_spec[field] > template[field] > library_default.
The library default lookup happens at the call site (`render_*`),
not here — this module only resolves explicit vs template.
"""
from __future__ import annotations

from typing import Any, Callable

# A mapping entry returns: (spec_field, mapped_value, ok, reason).
# - spec_field: which field of the working spec receives the value.
# - mapped_value: the value to write (may be a dict for fan-out).
# - ok: True if the template value is recognized and applicable.
# - reason: when ok=False, why it was ignored.
MapResult = tuple[str | dict[str, Any], Any, bool, str]
Mapper = Callable[[Any], MapResult]


def _map_colormap_name(value: Any) -> MapResult:
    if not isinstance(value, str):
        return ("colormap", None, False, "colormap_name_not_string")
    return ("colormap", value, True, "")


def _map_colormap_kind(value: Any) -> MapResult:
    table = {
        "sequential":  ("colormap", "viridis"),
        "diverging":   ({"colormap": "RdBu_r", "vcenter": 0.0}, None),
        "categorical": ("colormap", "tab10"),
    }
    if value not in table:
        return ("colormap", None, False, "unknown_colormap_kind")
    field, val = table[value]
    if isinstance(field, dict):
        # Multi-field fan-out
        return (field, None, True, "")
    return (field, val, True, "")


def _map_vcenter(value: Any) -> MapResult:
    if not isinstance(value, (int, float)):
        return ("vcenter", None, False, "vcenter_not_number")
    return ("vcenter", float(value), True, "")


def _map_clip_pct(value: Any) -> MapResult:
    if not (isinstance(value, (list, tuple)) and len(value) == 2
            and all(isinstance(v, (int, float)) for v in value)):
        return ("clip_pct", None, False, "clip_pct_must_be_two_numbers")
    return ("clip_pct", [float(value[0]), float(value[1])], True, "")


_MAPPING: dict[str, Mapper] = {
    "colormap_name": _map_colormap_name,
    "colormap_kind": _map_colormap_kind,
    "vcenter":       _map_vcenter,
    "clip_pct":      _map_clip_pct,
}


def apply(
    spec: dict[str, Any], template: dict[str, Any] | None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply `template` to `spec` per the precedence rule.

    Returns (resolved, trace) where trace contains:
      - fields_applied: list[str] of template keys that wrote values
      - fields_ignored: list[{field, reason}]
    """
    resolved: dict[str, Any] = dict(spec)
    trace: dict[str, Any] = {"fields_applied": [], "fields_ignored": []}

    if template is None:
        return resolved, trace

    # colormap_name takes precedence over colormap_kind within a template:
    # if both present, drop colormap_kind first.
    seen_name = template.get("colormap_name") is not None
    for tmpl_field, value in template.items():
        if value is None:
            continue
        if tmpl_field == "colormap_kind" and seen_name:
            trace["fields_ignored"].append(
                {"field": tmpl_field,
                 "reason": "colormap_name_takes_precedence"})
            continue
        mapper = _MAPPING.get(tmpl_field)
        if mapper is None:
            trace["fields_ignored"].append(
                {"field": tmpl_field, "reason": "unknown_template_field"})
            continue
        spec_field, mapped_value, ok, reason = mapper(value)
        if not ok:
            trace["fields_ignored"].append(
                {"field": tmpl_field, "reason": reason})
            continue
        # Multi-field fan-out (dict spec_field carries {field: value} pairs)
        if isinstance(spec_field, dict):
            applied_any = False
            for sf, mv in spec_field.items():
                if sf in resolved and resolved[sf] is not None:
                    continue
                resolved[sf] = mv
                applied_any = True
            if applied_any:
                trace["fields_applied"].append(tmpl_field)
            else:
                trace["fields_ignored"].append(
                    {"field": tmpl_field,
                     "reason": "overridden_by_explicit_spec"})
            continue
        # Single-field write
        if spec_field in resolved and resolved[spec_field] is not None:
            trace["fields_ignored"].append(
                {"field": tmpl_field,
                 "reason": "overridden_by_explicit_spec"})
            continue
        resolved[spec_field] = mapped_value
        trace["fields_applied"].append(tmpl_field)

    return resolved, trace
```

- [ ] **Step 4: Run, verify green**

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/style.py \
        tests/mcp/plot_renderer/unit/test_style_application.py
git commit -m "cycle-2 task 16: style.apply with colormap mapping"
```

---

### Task 17: Projection family + layout fields + advisory fields

**Files:**
- Modify: `src/mcp/plot_renderer/style.py`
- Modify: `tests/mcp/plot_renderer/unit/test_style_application.py` (add cases)

- [ ] **Step 1: Write the failing test (append)**

Add to `test_style_application.py`:

```python
def test_projection_family_robinson():
    resolved, _ = apply({}, {"projection_family": "robinson"})
    assert resolved["projection"] == "Robinson"


def test_projection_family_polar_north():
    resolved, _ = apply({}, {"projection_family": "polar_stereo_north"})
    assert resolved["projection"] == "NorthPolarStereo"


def test_projection_family_unknown_ignored():
    resolved, trace = apply({}, {"projection_family": "weird"})
    assert "projection" not in resolved
    assert any(f["field"] == "projection_family" for f in trace["fields_ignored"])


def test_layout_fields():
    resolved, _ = apply({}, {
        "colorbar_position": "bottom",
        "legend_placement": "outside_right",
        "gridlines": "heavy",
        "aspect": 1.5,
    })
    assert resolved["colorbar_position"] == "bottom"
    assert resolved["legend_placement"] == "outside_right"
    assert resolved["gridlines"] == "heavy"
    assert resolved["aspect"] == 1.5


def test_font_scale_clamped():
    # Below range
    resolved, _ = apply({}, {"font_scale": 0.3})
    assert resolved["font_scale"] == 0.7
    # Above range
    resolved, _ = apply({}, {"font_scale": 2.0})
    assert resolved["font_scale"] == 1.5


def test_advisory_fields_passthrough():
    resolved, _ = apply({}, {
        "extent_hint": "global",
        "title_placement": "top",
        "label_density": "verbose",
    })
    assert resolved.get("_advisory_extent_hint") == "global"
    assert resolved.get("_advisory_title_placement") == "top"
    assert resolved.get("_advisory_label_density") == "verbose"
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Extend `style.py` mapping table**

Add the new mappers and register them in `_MAPPING`:

```python
def _map_projection_family(value: Any) -> MapResult:
    table = {
        "plate_carree":        "PlateCarree",
        "robinson":            "Robinson",
        "polar_stereo_north":  "NorthPolarStereo",
        "polar_stereo_south":  "SouthPolarStereo",
        "lambert_conformal":   "LambertConformal",
        "mercator":            "Mercator",
    }
    if value not in table:
        return ("projection", None, False, "unknown_projection_family")
    return ("projection", table[value], True, "")


def _map_colorbar_position(value: Any) -> MapResult:
    if value not in {"right", "left", "top", "bottom", "none"}:
        return ("colorbar_position", None, False, "unknown_colorbar_position")
    return ("colorbar_position", value, True, "")


def _map_legend_placement(value: Any) -> MapResult:
    if value not in {"best", "outside_right", "outside_bottom", "none"}:
        return ("legend_placement", None, False, "unknown_legend_placement")
    return ("legend_placement", value, True, "")


def _map_gridlines(value: Any) -> MapResult:
    if value not in {"none", "light", "heavy"}:
        return ("gridlines", None, False, "unknown_gridlines")
    return ("gridlines", value, True, "")


def _map_aspect(value: Any) -> MapResult:
    if value == "auto":
        return ("aspect", "auto", True, "")
    if isinstance(value, (int, float)):
        return ("aspect", float(value), True, "")
    return ("aspect", None, False, "aspect_not_number_or_auto")


def _map_font_scale(value: Any) -> MapResult:
    if not isinstance(value, (int, float)):
        return ("font_scale", None, False, "font_scale_not_number")
    clamped = max(0.7, min(1.5, float(value)))
    return ("font_scale", clamped, True, "")


def _map_advisory(field_name: str) -> Mapper:
    """Generator for advisory fields that flow through with a `_advisory_` prefix."""
    def _inner(value: Any) -> MapResult:
        return (f"_advisory_{field_name}", value, True, "")
    return _inner


_MAPPING.update({
    "projection_family":  _map_projection_family,
    "colorbar_position":  _map_colorbar_position,
    "legend_placement":   _map_legend_placement,
    "gridlines":          _map_gridlines,
    "aspect":             _map_aspect,
    "font_scale":         _map_font_scale,
    "extent_hint":        _map_advisory("extent_hint"),
    "title_placement":    _map_advisory("title_placement"),
    "label_density":      _map_advisory("label_density"),
})
```

- [ ] **Step 4: Run, verify green**

Expected: all tests in `test_style_application.py` pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/style.py \
        tests/mcp/plot_renderer/unit/test_style_application.py
git commit -m "cycle-2 task 17: style projection/layout/advisory mappings"
```

---

### Task 18: Unknown-field handling + provenance pass-through

**Files:**
- Modify: `src/mcp/plot_renderer/style.py`
- Create: `tests/mcp/plot_renderer/unit/test_style_template_unknown.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_style_template_unknown.py
from src.mcp.plot_renderer.style import apply, source_provenance


def test_unknown_field_recorded():
    resolved, trace = apply({}, {"warp_speed": "9001"})
    assert any(f["field"] == "warp_speed" and
               f["reason"] == "unknown_template_field"
               for f in trace["fields_ignored"])


def test_empty_template_is_noop():
    resolved, trace = apply({"existing": "yes"}, {})
    assert resolved == {"existing": "yes"}
    assert trace["fields_applied"] == []
    assert trace["fields_ignored"] == []


def test_none_template_is_noop():
    resolved, trace = apply({"a": 1}, None)
    assert resolved == {"a": 1}
    assert trace["fields_applied"] == []


def test_source_provenance_extracted():
    template = {
        "colormap_kind": "sequential",
        "source": {
            "image_path": "/data/ref.png",
            "extracted_by": "claude-opus-4-7",
            "extracted_at": "2026-05-07T12:00:00Z",
            "confidence": 0.85,
        },
    }
    src = source_provenance(template)
    assert src is not None
    assert src["image_path"] == "/data/ref.png"
    assert src["confidence"] == 0.85


def test_source_provenance_missing_returns_none():
    assert source_provenance({"colormap_kind": "sequential"}) is None
    assert source_provenance(None) is None
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `style.py`**

```python
def source_provenance(template: dict[str, Any] | None) -> dict[str, Any] | None:
    """Extract the optional `source` provenance block from a style_template.

    Returns None if absent. The renderer flows this block untouched into
    `oracle.style_template_applied.source`.
    """
    if template is None:
        return None
    src = template.get("source")
    if not isinstance(src, dict):
        return None
    return dict(src)
```

Note: the unknown-field handling already exists in `apply()` — Task 16
implemented it. The test in Step 1 verifies that path is reachable.
The new code here is `source_provenance` only.

- [ ] **Step 4: Run, verify green**

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/style.py \
        tests/mcp/plot_renderer/unit/test_style_template_unknown.py
git commit -m "cycle-2 task 18: style unknown-field trace + source_provenance helper"
```

---

### Task 19: Phase-4 lint and typecheck gate

- [ ] **Step 1: Run ruff**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer
```

- [ ] **Step 2: Run mypy**

```bash
.venv/bin/mypy src/mcp/plot_renderer
```

- [ ] **Step 3: Run plot_renderer tests**

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

- [ ] **Step 4: Commit if any fixes**

```bash
git add -A
git commit -m "cycle-2 phase-4 gate: lint + typecheck clean"
```

---

## Phase 5: Lifecycle (output path resolution + atomic save)

Phase 5 owns where figures land and how they get written. Spec §5.

### Task 20: Output path resolution + auto-name

**Files:**
- Create: `src/mcp/plot_renderer/lifecycle.py` (initial; grows in Task 21)
- Create: `tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py
import json
from pathlib import Path

from src.mcp.plot_renderer.lifecycle import (
    resolve_output_path, auto_name,
    OutputPathInvalid, FormatExtensionMismatch,
)


def test_explicit_absolute_path(tmp_path):
    target = tmp_path / "out.png"
    p = resolve_output_path(str(target), fmt="png")
    assert Path(p) == target


def test_explicit_relative_resolves_against_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = resolve_output_path("rel/out.png", fmt="png")
    assert Path(p).is_absolute()
    assert Path(p).name == "out.png"


def test_explicit_format_extension_mismatch(tmp_path):
    target = tmp_path / "out.png"
    try:
        resolve_output_path(str(target), fmt="pdf")
    except FormatExtensionMismatch:
        return
    raise AssertionError("expected FormatExtensionMismatch")


def test_explicit_format_inferred_from_extension(tmp_path):
    target = tmp_path / "out.svg"
    p = resolve_output_path(str(target), fmt=None)
    assert p.endswith(".svg")


def test_auto_name_basic(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="map", spec={"variable": "tos",
                                     "title": "SST",
                                     "values": [[1.0]],
                                     "lat": [0.0], "lon": [0.0]},
                  fmt="png")
    assert ".ncplot/figures/" in p
    assert p.endswith(".png")
    assert "map_tos_" in p


def test_auto_name_uses_title_slug_when_no_variable(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="timeseries",
                  spec={"title": "Annual Mean", "series": []},
                  fmt="pdf")
    assert "timeseries_annual-mean_" in p
    assert p.endswith(".pdf")


def test_auto_name_falls_back_to_plot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = auto_name(tool="profile", spec={}, fmt="png")
    assert "profile_plot_" in p


def test_auto_name_hash_disambiguates(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p1 = auto_name(tool="map",
                   spec={"variable": "v", "values": [[1.0]],
                         "lat": [0.0], "lon": [0.0],
                         "colormap": "viridis"},
                   fmt="png")
    p2 = auto_name(tool="map",
                   spec={"variable": "v", "values": [[1.0]],
                         "lat": [0.0], "lon": [0.0],
                         "colormap": "magma"},
                   fmt="png")
    assert p1 != p2  # different specs → different hashes
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `lifecycle.py` (path-resolution-only)**

```python
# src/mcp/plot_renderer/lifecycle.py
"""⤴ format-agnostic — eligible for _core/ lift.

Output path resolution + auto-name + atomic save (Task 21).
Owns where figures land and how they get written (spec §5).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any


_SUPPORTED_FORMATS = {"png", "pdf", "svg"}
_SLUG_RE = re.compile(r"[^a-zA-Z0-9]+")
_AUTO_DIR = ".ncplot/figures"


class OutputPathInvalid(ValueError):
    pass


class FormatExtensionMismatch(ValueError):
    pass


class UnsupportedFormat(ValueError):
    pass


def _ext_from_path(path: str) -> str | None:
    suffix = Path(path).suffix.lower().lstrip(".")
    return suffix or None


def _slug(s: str) -> str:
    s = _SLUG_RE.sub("-", s.strip().lower())
    return s.strip("-") or "plot"


def _spec_hash(spec: dict[str, Any]) -> str:
    """First 6 chars of sha256(canonical_json(spec))."""
    payload = json.dumps(spec, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()[:6]


def _when_token(spec: dict[str, Any]) -> str:
    """Best-effort first-time-coord token for auto-naming."""
    # render_map inline form
    coords = spec.get("coords") or {}
    times = coords.get("time") if isinstance(coords, dict) else None
    if not times:
        # render_timeseries: find earliest time across series
        series = spec.get("series")
        if isinstance(series, list) and series:
            ts = []
            for s in series:
                t = s.get("time")
                if isinstance(t, list) and t:
                    ts.append(t[0])
            if ts:
                first = min(ts)
                return str(first)[:7] if "T" not in str(first) \
                       else str(first)[:10]
        if isinstance(spec.get("time"), list) and spec["time"]:
            first = spec["time"][0]
            return str(first)[:10]
        if isinstance(series, list) and len(series) > 1:
            return "multi"
        return "unknown"
    if isinstance(times, list) and times:
        return str(times[0])[:10]
    return "unknown"


def resolve_output_path(
    output_path: str, fmt: str | None,
) -> str:
    """Validate explicit path and return absolute resolved path."""
    if not output_path:
        raise OutputPathInvalid("output_path must be a non-empty string")
    p = Path(output_path)
    if not p.is_absolute():
        p = Path.cwd() / p
    ext = _ext_from_path(str(p))
    if ext is None:
        raise OutputPathInvalid("output_path has no file extension")
    if ext not in _SUPPORTED_FORMATS:
        raise UnsupportedFormat(
            f"unsupported format {ext!r}; supported: {sorted(_SUPPORTED_FORMATS)}")
    if fmt is not None and fmt != ext:
        raise FormatExtensionMismatch(
            f"format={fmt!r} disagrees with extension {ext!r}")
    return str(p)


def auto_name(*, tool: str, spec: dict[str, Any], fmt: str) -> str:
    """Build an auto-name path under .ncplot/figures/."""
    if fmt not in _SUPPORTED_FORMATS:
        raise UnsupportedFormat(
            f"unsupported format {fmt!r}; supported: {sorted(_SUPPORTED_FORMATS)}")
    var = spec.get("variable")
    title = spec.get("title")
    if isinstance(var, str) and var:
        var_or_label = _slug(var)
    elif isinstance(title, str) and title:
        var_or_label = _slug(title)
    else:
        var_or_label = "plot"
    when = _when_token(spec)
    h = _spec_hash(spec)
    name = f"{tool}_{var_or_label}_{when}_{h}.{fmt}"
    return str(Path.cwd() / _AUTO_DIR / name)
```

- [ ] **Step 4: Run, verify green**

Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/lifecycle.py \
        tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py
git commit -m "cycle-2 task 20: lifecycle output_path resolution + auto_name"
```

---

### Task 21: Atomic save + parent dir creation + DPI validation

**Files:**
- Modify: `src/mcp/plot_renderer/lifecycle.py`
- Modify: `tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py` (new tests)

- [ ] **Step 1: Append failing tests**

```python
# Add to tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py
from pathlib import Path

import matplotlib.pyplot as plt
import pytest

from src.mcp.plot_renderer.lifecycle import (
    atomic_save, validate_dpi, InvalidDPI,
)


def test_validate_dpi_in_range():
    validate_dpi(150)
    validate_dpi(72)
    validate_dpi(600)


def test_validate_dpi_out_of_range():
    with pytest.raises(InvalidDPI):
        validate_dpi(50)
    with pytest.raises(InvalidDPI):
        validate_dpi(1000)


def test_atomic_save_writes_file_and_creates_parent(tmp_path):
    out = tmp_path / "deep" / "nested" / "out.png"
    fig = plt.figure()
    plt.plot([0, 1], [0, 1])
    size = atomic_save(fig, str(out), dpi=100)
    plt.close(fig)
    assert out.exists()
    assert size == out.stat().st_size
    assert size > 1000


def test_atomic_save_temp_file_cleaned_on_failure(tmp_path, monkeypatch):
    out = tmp_path / "out.png"
    fig = plt.figure()

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(fig, "savefig", boom)
    with pytest.raises(OSError):
        atomic_save(fig, str(out), dpi=100)
    plt.close(fig)
    # No .tmp leftover
    assert not (out.parent / (out.name + ".tmp")).exists()
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `lifecycle.py`**

```python
class InvalidDPI(ValueError):
    pass


def validate_dpi(dpi: int) -> None:
    if not isinstance(dpi, int):
        raise InvalidDPI(f"dpi must be int, got {type(dpi).__name__}")
    if dpi < 72 or dpi > 600:
        raise InvalidDPI(f"dpi {dpi} out of range [72, 600]")


def atomic_save(fig: Any, output_path: str, *, dpi: int) -> int:
    """Save the figure atomically: write to <path>.tmp then os.replace.
    On failure, remove the .tmp. Returns final file size in bytes.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + ".tmp")
    try:
        fig.savefig(tmp, dpi=dpi)
        os.replace(tmp, out)
    finally:
        if tmp.exists():
            try:
                tmp.unlink()
            except OSError:
                pass
    return out.stat().st_size
```

- [ ] **Step 4: Run, verify green**

Expected: 4 new tests + previous 8 = 12 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/lifecycle.py \
        tests/mcp/plot_renderer/unit/test_lifecycle_output_path.py
git commit -m "cycle-2 task 21: lifecycle atomic_save + validate_dpi"
```

---

### Task 22: Phase-5 lint and typecheck gate

- [ ] **Step 1: Run ruff, mypy, full plot_renderer test suite**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer && \
.venv/bin/mypy src/mcp/plot_renderer && \
.venv/bin/pytest tests/mcp/plot_renderer -v
```

- [ ] **Step 2: Commit if any fixes**

```bash
git add -A && git commit -m "cycle-2 phase-5 gate: lint + typecheck clean"
```

---

## Phase 6: Render-oracle JSON

The oracle is the renderer's observable behavior in machine-readable
form (spec §6). It lands in `result.oracle` for production calls and
optionally as a sidecar JSON next to the figure for tests/debug.

### Task 23: Oracle schema + common-field capture

**Files:**
- Create: `src/mcp/plot_renderer/oracle.py` (initial; grows in Task 24)
- Create: `tests/mcp/plot_renderer/unit/test_oracle_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_oracle_schema.py
import matplotlib.pyplot as plt
import pytest

from src.mcp.plot_renderer.oracle import (
    ORACLE_SCHEMA_VERSION, REQUIRED_TOP_LEVEL_FIELDS,
    OracleIncomplete, capture_common,
)


def test_schema_version_pinned():
    assert ORACLE_SCHEMA_VERSION == 1


def test_required_top_level_fields():
    expected = {"oracle_schema_version", "tool", "output", "data",
                "style_resolution", "drawn", "style_template_applied"}
    assert REQUIRED_TOP_LEVEL_FIELDS == expected


def test_capture_common_minimal():
    fig = plt.figure(figsize=(4, 3))
    plt.plot([0, 1], [0, 1])
    oracle = capture_common(
        fig=fig,
        tool="render_timeseries",
        resolved_spec={"colormap": "viridis", "dpi": 150,
                       "format": "png", "aspect": "auto",
                       "font_scale": 1.0, "colorbar_position": "none",
                       "gridlines": "light"},
        style_resolution_sources={
            "colormap": "library_default",
            "colorbar_position": "explicit",
            "gridlines": "library_default",
            "font_scale": "library_default",
            "aspect": "library_default",
        },
        safety_actions={
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": 0.0, "vmax_used": 1.0,
            "nan_fraction": 0.0,
        },
        output_path="/tmp/x.png",
        output_size_bytes=12345,
        data_shape=[2],
    )
    plt.close(fig)
    assert oracle["oracle_schema_version"] == 1
    assert oracle["tool"] == "render_timeseries"
    assert oracle["output"]["path"] == "/tmp/x.png"
    assert oracle["output"]["format"] == "png"
    assert oracle["output"]["dpi"] == 150
    assert oracle["data"]["shape"] == [2]
    assert oracle["style_resolution"]["colormap"]["source"] == "library_default"


def test_oracle_incomplete_when_missing_required():
    fig = plt.figure()
    with pytest.raises(OracleIncomplete):
        capture_common(
            fig=fig, tool="render_map",
            resolved_spec={},  # missing several presentation fields
            style_resolution_sources={},  # incomplete
            safety_actions={},
            output_path="/tmp/x.png",
            output_size_bytes=1, data_shape=[1, 1],
        )
    plt.close(fig)
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `oracle.py` (common capture only)**

```python
# src/mcp/plot_renderer/oracle.py
"""⤴ format-agnostic — eligible for _core/ lift.

Render-oracle JSON capture. Spec §6.

Per-tool drawn fields are added in Task 24. This module exposes
common helpers; tools call `capture_common` then enrich with their
own `drawn` fields and call `finalize`.
"""
from __future__ import annotations

from typing import Any


ORACLE_SCHEMA_VERSION = 1

REQUIRED_TOP_LEVEL_FIELDS = {
    "oracle_schema_version", "tool", "output", "data",
    "style_resolution", "drawn", "style_template_applied",
}

# Minimum presentation fields present in every resolved spec
_REQUIRED_PRESENTATION_FIELDS = {
    "colormap", "colorbar_position", "gridlines", "font_scale", "aspect",
}


class OracleIncomplete(RuntimeError):
    pass


def _output_block(fig: Any, output_path: str, size_bytes: int,
                  fmt: str | None, dpi: int | None) -> dict[str, Any]:
    width_px = int(fig.get_size_inches()[0] * (dpi or 100))
    height_px = int(fig.get_size_inches()[1] * (dpi or 100))
    if fmt is None:
        from pathlib import Path
        fmt = Path(output_path).suffix.lstrip(".") or "png"
    return {
        "path": output_path,
        "format": fmt,
        "size_bytes": size_bytes,
        "dpi": dpi or 0,
        "width_px": width_px,
        "height_px": height_px,
    }


def _style_resolution_block(
    sources: dict[str, str], resolved: dict[str, Any],
) -> dict[str, Any]:
    block: dict[str, Any] = {}
    for field in _REQUIRED_PRESENTATION_FIELDS:
        if field not in sources:
            raise OracleIncomplete(
                f"style_resolution missing source for required field {field!r}")
        block[field] = {"value": resolved.get(field),
                         "source": sources[field]}
    # Optional fields if present:
    for field in ("projection",):
        if field in resolved or field in sources:
            block[field] = {"value": resolved.get(field),
                             "source": sources.get(field, "library_default")}
    return block


def capture_common(*,
    fig: Any, tool: str,
    resolved_spec: dict[str, Any],
    style_resolution_sources: dict[str, str],
    safety_actions: dict[str, Any],
    output_path: str, output_size_bytes: int,
    data_shape: list[int],
) -> dict[str, Any]:
    """Build the common (non-tool-specific) oracle skeleton.

    Tools enrich `drawn` with their own per-tool fields and set
    `style_template_applied` before sending the oracle out.
    """
    out_block = _output_block(
        fig, output_path, output_size_bytes,
        fmt=resolved_spec.get("format"),
        dpi=resolved_spec.get("dpi"),
    )
    return {
        "oracle_schema_version": ORACLE_SCHEMA_VERSION,
        "tool": tool,
        "output": out_block,
        "data": {
            "shape": list(data_shape),
            "plotted_min": safety_actions.get("plotted_min"),
            "plotted_max": safety_actions.get("plotted_max"),
            "nan_fraction": safety_actions.get("nan_fraction", 0.0),
            "applied_downsample": safety_actions.get("applied_downsample"),
            "applied_lon_shift": safety_actions.get("applied_lon_shift"),
            "applied_clip_pct": safety_actions.get("applied_clip_pct"),
            "vmin_used": safety_actions.get("vmin_used"),
            "vmax_used": safety_actions.get("vmax_used"),
        },
        "style_resolution": _style_resolution_block(
            style_resolution_sources, resolved_spec),
        "drawn": {},   # tool fills in
        "style_template_applied": None,   # tool fills in
    }


def finalize(oracle: dict[str, Any]) -> dict[str, Any]:
    """Validate the oracle has all required top-level fields. Raises
    OracleIncomplete if not."""
    missing = REQUIRED_TOP_LEVEL_FIELDS - set(oracle.keys())
    if missing:
        raise OracleIncomplete(
            f"oracle missing required top-level fields: {sorted(missing)}")
    return oracle
```

- [ ] **Step 4: Run, verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/oracle.py \
        tests/mcp/plot_renderer/unit/test_oracle_schema.py
git commit -m "cycle-2 task 23: oracle schema + capture_common"
```

---

### Task 24: Per-tool drawn-field hooks + style_template_applied

**Files:**
- Modify: `src/mcp/plot_renderer/oracle.py`
- Modify: `tests/mcp/plot_renderer/unit/test_oracle_schema.py` (add tests)

- [ ] **Step 1: Append failing tests**

```python
# Add to tests/mcp/plot_renderer/unit/test_oracle_schema.py
import matplotlib.pyplot as plt

from src.mcp.plot_renderer.oracle import (
    drawn_for_timeseries, drawn_for_profile, drawn_for_map,
    style_template_applied_block, finalize,
)


def test_drawn_for_timeseries():
    fig, ax = plt.subplots()
    ax.set_title("Annual mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("°C")
    ax.plot([0, 1], [0, 1], label="A", color="C0", linestyle="-")
    ax.legend()
    drawn = drawn_for_timeseries(
        fig=fig, ax=ax,
        series_meta=[{"label": "A", "n_points": 2,
                       "color": "C0", "linestyle": "-"}],
        trendline_kind=None,
    )
    plt.close(fig)
    assert drawn["title"] == "Annual mean"
    assert drawn["axis_labels"]["x"] == "Year"
    assert drawn["axis_labels"]["y"] == "°C"
    assert drawn["legend_present"] is True
    assert drawn["series_count"] == 1
    assert drawn["series"][0]["label"] == "A"
    assert drawn["trendline_present"] is False


def test_drawn_for_profile_log_scale_invert():
    fig, ax = plt.subplots()
    ax.set_yscale("log")
    ax.invert_yaxis()
    ax.plot([280.0, 220.0], [1000.0, 100.0], label="P", color="C1")
    drawn = drawn_for_profile(
        fig=fig, ax=ax, vertical_axis="y",
        series_meta=[{"label": "P", "n_points": 2,
                       "color": "C1", "linestyle": "-"}],
    )
    plt.close(fig)
    assert drawn["log_scale"] is True
    assert drawn["invert_pressure"] is True
    assert drawn["vertical_axis"] == "y"


def test_style_template_applied_block_with_template():
    block = style_template_applied_block(
        template={"colormap_kind": "diverging",
                  "source": {"image_path": "x.png",
                              "extracted_by": "claude",
                              "extracted_at": "2026-05-07T00:00:00Z",
                              "confidence": 0.9}},
        trace={"fields_applied": ["colormap_kind"], "fields_ignored": []},
    )
    assert block is not None
    assert "colormap_kind" in block["fields_applied"]
    assert block["source"]["image_path"] == "x.png"


def test_style_template_applied_block_with_none_template():
    assert style_template_applied_block(template=None, trace={"fields_applied": [], "fields_ignored": []}) is None


def test_finalize_passes_when_all_required_present():
    oracle = {
        "oracle_schema_version": 1, "tool": "render_map",
        "output": {}, "data": {}, "style_resolution": {},
        "drawn": {"title": None}, "style_template_applied": None,
    }
    out = finalize(oracle)
    assert out is oracle
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Append to `oracle.py`**

```python
def _series_meta_block(series_meta: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"label": s.get("label"),
         "n_points": s.get("n_points"),
         "line_color": s.get("color"),
         "line_style": s.get("linestyle")}
        for s in series_meta
    ]


def drawn_for_timeseries(*,
    fig: Any, ax: Any,
    series_meta: list[dict[str, Any]],
    trendline_kind: str | None,
) -> dict[str, Any]:
    legend = ax.get_legend()
    return {
        "title": ax.get_title() or None,
        "colorbar_label": None,
        "axis_labels": {"x": ax.get_xlabel() or None,
                        "y": ax.get_ylabel() or None},
        "legend_present": legend is not None,
        "legend_entries": [t.get_text() for t in legend.get_texts()]
                           if legend is not None else None,
        "gridlines_drawn": any(line.get_visible()
                               for line in ax.get_xgridlines() + ax.get_ygridlines()),
        "series_count": len(series_meta),
        "series": _series_meta_block(series_meta),
        "trendline_present": trendline_kind is not None,
        "trendline_kind": trendline_kind,
    }


def drawn_for_profile(*,
    fig: Any, ax: Any, vertical_axis: str,
    series_meta: list[dict[str, Any]],
) -> dict[str, Any]:
    if vertical_axis == "y":
        log_scale = ax.get_yscale() == "log"
        invert = ax.yaxis_inverted()
    else:
        log_scale = ax.get_xscale() == "log"
        invert = ax.xaxis_inverted()
    legend = ax.get_legend()
    return {
        "title": ax.get_title() or None,
        "axis_labels": {"x": ax.get_xlabel() or None,
                        "y": ax.get_ylabel() or None},
        "legend_present": legend is not None,
        "legend_entries": [t.get_text() for t in legend.get_texts()]
                           if legend is not None else None,
        "gridlines_drawn": any(line.get_visible()
                               for line in ax.get_xgridlines() + ax.get_ygridlines()),
        "series_count": len(series_meta),
        "series": _series_meta_block(series_meta),
        "vertical_axis": vertical_axis,
        "log_scale": log_scale,
        "invert_pressure": invert,
    }


def drawn_for_map(*,
    fig: Any, ax: Any,
    projection_class: str | None,
    extent: list[float] | None,
    coastlines_drawn: bool,
    colorbar_label: str | None,
) -> dict[str, Any]:
    return {
        "title": ax.get_title() or None,
        "colorbar_label": colorbar_label,
        "axis_labels": {"x": ax.get_xlabel() or None,
                        "y": ax.get_ylabel() or None},
        "legend_present": False,
        "legend_entries": None,
        "gridlines_drawn": True,  # cartopy gridliner is separate; tracked via spec
        "coastlines_drawn": coastlines_drawn,
        "projection_class": projection_class,
        "extent": extent,
    }


def style_template_applied_block(*,
    template: dict[str, Any] | None,
    trace: dict[str, Any],
) -> dict[str, Any] | None:
    if template is None:
        return None
    src = None
    if isinstance(template.get("source"), dict):
        src = dict(template["source"])
    return {
        "fields_applied": list(trace.get("fields_applied", [])),
        "fields_ignored": list(trace.get("fields_ignored", [])),
        "source": src,
    }
```

- [ ] **Step 4: Run, verify green**

Expected: all oracle tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/oracle.py \
        tests/mcp/plot_renderer/unit/test_oracle_schema.py
git commit -m "cycle-2 task 24: oracle drawn_for_* hooks + style_template_applied_block"
```

---

### Task 25: Phase-6 lint and typecheck gate

- [ ] **Step 1: Run ruff, mypy, plot_renderer tests**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer && \
.venv/bin/mypy src/mcp/plot_renderer && \
.venv/bin/pytest tests/mcp/plot_renderer -v
```

- [ ] **Step 2: Commit if any fixes**

```bash
git add -A && git commit -m "cycle-2 phase-6 gate: lint + typecheck clean"
```

---

## Phase 7: Per-tool render

Phase 7 builds the three callable tools. Order: simplest first
(timeseries → profile → map). Each tool wires together adapter →
style → safety → matplotlib drawing → lifecycle save → oracle.

### Task 26: `render_timeseries` — single + multi-series

**Files:**
- Create: `src/mcp/plot_renderer/tools/__init__.py` (empty marker)
- Create: `src/mcp/plot_renderer/tools/render_timeseries.py`
- Create: `tests/mcp/plot_renderer/unit/test_render_timeseries.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_render_timeseries.py
from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries


def test_single_series_sugar(tmp_path, monkeypatch, small_timeseries):
    monkeypatch.chdir(tmp_path)
    spec = {**small_timeseries,
            "title": "Demo", "ylabel": "v", "xlabel": "Year"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    out = env["result"]
    assert out["output_path"].endswith(".png")
    assert out["file_size_bytes"] > 1000
    assert out["series_count"] == 1
    assert out["oracle"]["drawn"]["title"] == "Demo"
    assert out["oracle"]["drawn"]["series_count"] == 1


def test_multi_series_legend(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [1.0, 2.0],
         "time": ["2024-01-15", "2024-02-15"], "label": "A"},
        {"values": [2.0, 3.0],
         "time": ["2024-01-15", "2024-02-15"], "label": "B"},
    ], "title": "Multi"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert env["result"]["series_count"] == 2
    assert env["result"]["oracle"]["drawn"]["legend_present"] is True


def test_invalid_spec_returns_error_envelope(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = render_timeseries({})
    assert env["ok"] is False
    assert env["error"]["code"] == "invalid_spec"


def test_color_cycle_warning_when_over_10_series(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [float(i)], "time": ["2024-01-15"], "label": f"S{i}"}
        for i in range(11)
    ]}
    env = render_timeseries(spec)
    assert env["ok"] is True
    codes = [w["code"] for w in env["warnings"]]
    assert "color_cycle_exceeded" in codes
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `render_timeseries.py`**

```python
# src/mcp/plot_renderer/tools/__init__.py — leave empty (just a marker)
```

```python
# src/mcp/plot_renderer/tools/render_timeseries.py
"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, defaults as _defaults, envelope, lifecycle, oracle, style,
)
from src.mcp.plot_renderer.envelope import WarningCode


def _resolve_presentation(resolved: dict[str, Any]) -> dict[str, Any]:
    """Fill in remaining presentation fields with library defaults."""
    out = dict(resolved)
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    out.setdefault("colorbar_position", "none")  # timeseries has no colorbar
    return out


def _style_resolution_sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "colorbar_position", "gridlines",
                  "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied or any(f.startswith(field) for f in applied):
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def render_timeseries(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 1D time series (single or multi). See spec §2.2."""
    warnings: list[dict[str, Any]] = []
    try:
        # 1. Spec validation + data normalization
        try:
            series = adapter.normalize_1d_series(spec, axis_name="time")
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        # 2. Style application
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved)

        # 3. Multi-series color cycle warning
        if len(series) > 10:
            warnings.append(envelope.warn(
                WarningCode.COLOR_CYCLE_EXCEEDED,
                f"{len(series)} series exceeds 10-color default cycle; using tab20",
                {"series_count": len(series)}))

        # 4. Render
        fig, ax = plt.subplots(figsize=(8.0, 4.5))
        if len(series) > 10:
            color_cycle = plt.colormaps["tab20"].colors
        else:
            color_cycle = plt.colormaps["tab10"].colors
        per_series_meta: list[dict[str, Any]] = []
        per_series_stats: list[dict[str, Any]] = []
        for i, s in enumerate(series):
            color = s.get("color") or color_cycle[i % len(color_cycle)]
            line, = ax.plot(s["axis"], s["values"], label=s["label"],
                             color=color, linestyle="-")
            per_series_meta.append({
                "label": s["label"], "n_points": int(s["values"].shape[0]),
                "color": str(color), "linestyle": "-",
            })
            finite = s["values"][np.isfinite(s["values"])]
            per_series_stats.append({
                "label": s["label"],
                "n_points": int(s["values"].shape[0]),
                "plotted_min": float(finite.min()) if finite.size else None,
                "plotted_max": float(finite.max()) if finite.size else None,
                "nan_fraction": (
                    1.0 - float(finite.size) / float(s["values"].size)
                    if s["values"].size else 0.0),
            })
        if spec.get("title"):
            ax.set_title(spec["title"])
        if spec.get("xlabel"):
            ax.set_xlabel(spec["xlabel"])
        if spec.get("ylabel"):
            ax.set_ylabel(spec["ylabel"])
        if len(series) > 1 or resolved.get("legend_placement") not in (None, "none"):
            ax.legend()
        ax.grid(resolved.get("gridlines") != "none", alpha=0.3)
        fig.tight_layout()

        # 5. Output
        fmt = resolved.get("format", "png")
        dpi = int(resolved.get("dpi", 150))
        lifecycle.validate_dpi(dpi)
        if spec.get("output_path"):
            try:
                output_path = lifecycle.resolve_output_path(
                    spec["output_path"], fmt=spec.get("format"))
            except lifecycle.FormatExtensionMismatch as e:
                plt.close(fig)
                return envelope.error("format_extension_mismatch", str(e))
            except lifecycle.UnsupportedFormat as e:
                plt.close(fig)
                return envelope.error("unsupported_format", str(e))
            except lifecycle.OutputPathInvalid as e:
                plt.close(fig)
                return envelope.error("output_path_invalid", str(e))
        else:
            output_path = lifecycle.auto_name(tool="timeseries", spec=spec, fmt=fmt)

        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        # 6. Oracle
        sources = _style_resolution_sources(spec, trace)
        sa = {
            "plotted_min": min(
                (s["plotted_min"] for s in per_series_stats if s["plotted_min"] is not None),
                default=None),
            "plotted_max": max(
                (s["plotted_max"] for s in per_series_stats if s["plotted_max"] is not None),
                default=None),
            "nan_fraction": (
                sum(s["nan_fraction"] for s in per_series_stats) / len(per_series_stats)
                if per_series_stats else 0.0),
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": None, "vmax_used": None,
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_timeseries",
            resolved_spec=resolved,
            style_resolution_sources=sources,
            safety_actions=sa,
            output_path=output_path,
            output_size_bytes=size_bytes,
            data_shape=[len(series)],
        )
        ocl["drawn"] = oracle.drawn_for_timeseries(
            fig=fig, ax=ax, series_meta=per_series_meta,
            trendline_kind=spec.get("trendline"))
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "series_count": len(series),
            "series": per_series_stats,
            "oracle": ocl,
        }, warnings=warnings)

    except Exception as e:
        # Catch-all: never let a raw exception escape
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
```

- [ ] **Step 4: Run, verify green**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_render_timeseries.py -v
```

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/tools/__init__.py \
        src/mcp/plot_renderer/tools/render_timeseries.py \
        tests/mcp/plot_renderer/unit/test_render_timeseries.py
git commit -m "cycle-2 task 26: render_timeseries (single + multi-series)"
```

---

### Task 27: `render_timeseries` — trendline (linear + lowess)

**Files:**
- Modify: `src/mcp/plot_renderer/tools/render_timeseries.py`
- Modify: `tests/mcp/plot_renderer/unit/test_render_timeseries.py` (add tests)

- [ ] **Step 1: Append failing tests**

```python
# Add to tests/mcp/plot_renderer/unit/test_render_timeseries.py
def test_linear_trendline(tmp_path, monkeypatch, small_timeseries):
    monkeypatch.chdir(tmp_path)
    spec = {**small_timeseries, "trendline": "linear"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["trendline_present"] is True
    assert env["result"]["oracle"]["drawn"]["trendline_kind"] == "linear"


def test_lowess_without_scipy_returns_error(monkeypatch, tmp_path, small_timeseries):
    monkeypatch.chdir(tmp_path)
    # Force the scipy import path to fail.
    import sys
    monkeypatch.setitem(sys.modules, "scipy", None)
    monkeypatch.setitem(sys.modules, "scipy.signal", None)
    spec = {**small_timeseries, "trendline": "lowess"}
    env = render_timeseries(spec)
    assert env["ok"] is False
    assert env["error"]["code"] == "trendline_dependency_missing"
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Modify `render_timeseries.py`**

Insert this helper near the top of the file (after the existing imports):

```python
def _apply_trendline(ax, x_axis, values, kind: str) -> None:
    """Add a trendline to `ax`. `kind` ∈ {"linear", "lowess"}."""
    if kind == "linear":
        # Convert datetime64 to ordinal seconds for fitting
        if np.issubdtype(np.asarray(x_axis).dtype, np.datetime64):
            x_num = np.asarray(x_axis, dtype="datetime64[s]").astype("float64")
        else:
            x_num = np.asarray(x_axis, dtype="float64")
        finite = np.isfinite(values) & np.isfinite(x_num)
        if finite.sum() < 2:
            return
        coeffs = np.polyfit(x_num[finite], values[finite], 1)
        ax.plot(x_axis, np.polyval(coeffs, x_num),
                color="black", linestyle="--", linewidth=1.0)
    elif kind == "lowess":
        try:
            from scipy.signal import savgol_filter  # noqa: F401
        except (ImportError, ModuleNotFoundError) as e:
            raise _LowessUnavailable(
                "scipy is required for lowess trendline; install with `uv pip install scipy`"
            ) from e
        # Use savgol as a smooth lowess-like estimate
        from scipy.signal import savgol_filter
        n = values.shape[0]
        window = max(5, n // 10)
        if window % 2 == 0:
            window += 1
        if window > n:
            return
        smoothed = savgol_filter(values, window_length=window, polyorder=2,
                                  mode="nearest")
        ax.plot(x_axis, smoothed,
                color="black", linestyle="--", linewidth=1.0)


class _LowessUnavailable(RuntimeError):
    pass
```

Then in `render_timeseries`, after the per-series plotting loop and BEFORE
`fig.tight_layout()`, add:

```python
        # Trendline (per spec §2.2)
        kind = spec.get("trendline")
        if kind in ("linear", "lowess"):
            try:
                # Apply on the first series only when single-series, on each
                # series otherwise (only render once for clarity in MVP: first).
                first = series[0]
                _apply_trendline(ax, first["axis"], first["values"], kind)
            except _LowessUnavailable as e:
                plt.close(fig)
                return envelope.error("trendline_dependency_missing", str(e))
```

- [ ] **Step 4: Run, verify green**

Expected: existing + 2 new tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/tools/render_timeseries.py \
        tests/mcp/plot_renderer/unit/test_render_timeseries.py
git commit -m "cycle-2 task 27: render_timeseries trendline (linear + lowess with scipy guard)"
```

---

### Task 28: `render_profile` — pressure-invert + log-scale + multi-series

**Files:**
- Create: `src/mcp/plot_renderer/tools/render_profile.py`
- Create: `tests/mcp/plot_renderer/unit/test_render_profile.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_render_profile.py
from src.mcp.plot_renderer.tools.render_profile import render_profile


def test_single_profile_pressure_log_invert(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "title": "T-profile", "xlabel": "T (K)"}
    env = render_profile(spec)
    assert env["ok"] is True
    drawn = env["result"]["oracle"]["drawn"]
    assert drawn["log_scale"] is True       # default for hPa
    assert drawn["invert_pressure"] is True
    assert drawn["vertical_axis"] == "y"
    assert drawn["title"] == "T-profile"
    assert env["result"]["series_count"] == 1


def test_meter_units_no_log_no_invert(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [288.0, 270.0, 250.0],
            "vertical": [0.0, 5000.0, 10000.0],
            "vertical_units": "m"}
    env = render_profile(spec)
    drawn = env["result"]["oracle"]["drawn"]
    assert drawn["log_scale"] is False
    assert drawn["invert_pressure"] is False


def test_multi_series_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"series": [
        {"values": [288.0, 250.0], "vertical": [1000.0, 500.0], "label": "A"},
        {"values": [285.0, 248.0], "vertical": [1000.0, 500.0], "label": "B"},
    ], "vertical_units": "hPa"}
    env = render_profile(spec)
    assert env["ok"] is True
    assert env["result"]["series_count"] == 2
    assert env["result"]["oracle"]["drawn"]["legend_present"] is True


def test_explicit_log_false_overrides_pressure_default(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "log_scale": False}
    env = render_profile(spec)
    assert env["result"]["oracle"]["drawn"]["log_scale"] is False


def test_explicit_invert_false(tmp_path, monkeypatch, small_profile):
    monkeypatch.chdir(tmp_path)
    spec = {**small_profile, "invert_pressure": False}
    env = render_profile(spec)
    assert env["result"]["oracle"]["drawn"]["invert_pressure"] is False
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `render_profile.py`**

```python
# src/mcp/plot_renderer/tools/render_profile.py
"""⤴ format-agnostic — eligible for _core/ lift."""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, defaults as _defaults, envelope, lifecycle, oracle, style,
)

_PRESSURE_UNITS = {"Pa", "hPa"}


def _resolve_presentation(resolved: dict[str, Any], is_pressure: bool) -> dict[str, Any]:
    out = dict(resolved)
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    if is_pressure:
        out.setdefault("log_scale", True)
        out.setdefault("invert_pressure", True)
    else:
        out.setdefault("log_scale", False)
        out.setdefault("invert_pressure", False)
    out.setdefault("colorbar_position", "none")
    out.setdefault("vertical_axis", "y")
    return out


def _sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "colorbar_position", "gridlines",
                   "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied:
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def render_profile(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a vertical profile (single or multi). See spec §2.3."""
    try:
        try:
            series = adapter.normalize_1d_series(spec, axis_name="vertical")
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        is_pressure = spec.get("vertical_units") in _PRESSURE_UNITS
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved, is_pressure)
        # User explicit overrides
        if "log_scale" in spec and spec["log_scale"] is not None:
            resolved["log_scale"] = spec["log_scale"]
        if "invert_pressure" in spec and spec["invert_pressure"] is not None:
            resolved["invert_pressure"] = spec["invert_pressure"]

        vertical_axis = spec.get("vertical_axis") or resolved["vertical_axis"]

        fig, ax = plt.subplots(figsize=(5.0, 6.0))
        color_cycle = plt.colormaps["tab10"].colors
        series_meta: list[dict[str, Any]] = []
        series_stats: list[dict[str, Any]] = []
        for i, s in enumerate(series):
            color = s.get("color") or color_cycle[i % len(color_cycle)]
            if vertical_axis == "y":
                ax.plot(s["values"], s["axis"], label=s["label"],
                        color=color, linestyle="-")
            else:
                ax.plot(s["axis"], s["values"], label=s["label"],
                        color=color, linestyle="-")
            series_meta.append({"label": s["label"],
                                  "n_points": int(s["values"].shape[0]),
                                  "color": str(color), "linestyle": "-"})
            finite = s["values"][np.isfinite(s["values"])]
            series_stats.append({"label": s["label"],
                                  "n_points": int(s["values"].shape[0]),
                                  "plotted_min": float(finite.min()) if finite.size else None,
                                  "plotted_max": float(finite.max()) if finite.size else None,
                                  "nan_fraction": (
                                      1.0 - float(finite.size) / float(s["values"].size)
                                      if s["values"].size else 0.0)})

        if resolved["log_scale"]:
            (ax.set_yscale if vertical_axis == "y" else ax.set_xscale)("log")
        if resolved["invert_pressure"]:
            (ax.invert_yaxis if vertical_axis == "y" else ax.invert_xaxis)()

        if spec.get("title"):
            ax.set_title(spec["title"])
        if spec.get("xlabel"):
            ax.set_xlabel(spec["xlabel"])
        if spec.get("ylabel"):
            ax.set_ylabel(spec["ylabel"])
        if len(series) > 1:
            ax.legend()
        ax.grid(resolved.get("gridlines") != "none", alpha=0.3)
        fig.tight_layout()

        fmt = resolved.get("format", "png")
        dpi = int(resolved.get("dpi", 150))
        lifecycle.validate_dpi(dpi)
        if spec.get("output_path"):
            try:
                output_path = lifecycle.resolve_output_path(
                    spec["output_path"], fmt=spec.get("format"))
            except lifecycle.FormatExtensionMismatch as e:
                plt.close(fig)
                return envelope.error("format_extension_mismatch", str(e))
            except lifecycle.UnsupportedFormat as e:
                plt.close(fig)
                return envelope.error("unsupported_format", str(e))
            except lifecycle.OutputPathInvalid as e:
                plt.close(fig)
                return envelope.error("output_path_invalid", str(e))
        else:
            output_path = lifecycle.auto_name(tool="profile", spec=spec, fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        sa = {
            "plotted_min": min(
                (s["plotted_min"] for s in series_stats if s["plotted_min"] is not None),
                default=None),
            "plotted_max": max(
                (s["plotted_max"] for s in series_stats if s["plotted_max"] is not None),
                default=None),
            "nan_fraction": (
                sum(s["nan_fraction"] for s in series_stats) / len(series_stats)
                if series_stats else 0.0),
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": None, "vmax_used": None,
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_profile",
            resolved_spec=resolved,
            style_resolution_sources=_sources(spec, trace),
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes, data_shape=[len(series)])
        ocl["drawn"] = oracle.drawn_for_profile(
            fig=fig, ax=ax, vertical_axis=vertical_axis,
            series_meta=series_meta)
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "series_count": len(series),
            "series": series_stats,
            "oracle": ocl,
        })
    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
```

- [ ] **Step 4: Run, verify green**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_render_profile.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/tools/render_profile.py \
        tests/mcp/plot_renderer/unit/test_render_profile.py
git commit -m "cycle-2 task 28: render_profile (pressure-invert + log + multi-series)"
```

---

### Task 29: `render_map` — cartopy guard + ambiguity envelope

**Files:**
- Create: `src/mcp/plot_renderer/tools/render_map.py` (initial; grows in Task 30)
- Create: `tests/mcp/plot_renderer/unit/test_render_map_no_cartopy.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_render_map_no_cartopy.py
from unittest.mock import patch

from src.mcp.plot_renderer.tools import render_map as rm


def test_cartopy_missing_returns_ambiguity_envelope(monkeypatch):
    monkeypatch.setattr(rm, "_CARTOPY_OK", False)
    monkeypatch.setattr(rm, "_CARTOPY_IMPORT_ERROR", "no module 'cartopy'")
    spec = {"values": [[1.0, 2.0], [3.0, 4.0]],
            "lat": [0.0, 1.0], "lon": [0.0, 1.0]}
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "cartopy_missing"
    assert any("cartopy" in c["value"]
               for c in env["error"]["candidates"])
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `render_map.py` (guard only; full drawing in Task 30)**

```python
# src/mcp/plot_renderer/tools/render_map.py
"""FORMAT-SPECIFIC (cartopy-aware): map rendering.

This is the only file in cycle-2 that imports cartopy. The seam test
allows it; other tools must not import cartopy.
"""
from __future__ import annotations

from typing import Any

from src.mcp.plot_renderer import envelope

try:
    import cartopy.crs as ccrs  # type: ignore[import-not-found]
    import cartopy.feature as cfeature  # type: ignore[import-not-found]
    _CARTOPY_OK = True
    _CARTOPY_IMPORT_ERROR: str | None = None
except ImportError as e:
    ccrs = None  # type: ignore[assignment]
    cfeature = None  # type: ignore[assignment]
    _CARTOPY_OK = False
    _CARTOPY_IMPORT_ERROR = str(e)


def _cartopy_ambiguity() -> dict[str, Any]:
    return envelope.ambiguous(
        subcode="cartopy_missing",
        message=("cartopy is not installed. Install with "
                 "`uv pip install cartopy` (PROJ + GEOS C libs required) or "
                 "wait for cycle-5 auto-install."),
        candidates=[
            {"param": "install", "value": "uv pip install cartopy",
             "kind": "shell_command"},
            {"param": "install", "value": "conda install -c conda-forge cartopy",
             "kind": "shell_command"},
        ],
        retry_with_param=None,
        context={"import_error": _CARTOPY_IMPORT_ERROR},
    )


def render_map(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 2D lat/lon map. See spec §2.1."""
    if not _CARTOPY_OK:
        return _cartopy_ambiguity()
    # Drawing implementation lands in Task 30
    return envelope.error("internal_render_error",
                          "render_map drawing not implemented yet")
```

- [ ] **Step 4: Run, verify green**

Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/tools/render_map.py \
        tests/mcp/plot_renderer/unit/test_render_map_no_cartopy.py
git commit -m "cycle-2 task 29: render_map cartopy guard + ambiguity envelope"
```

---

### Task 30: `render_map` — projection + drawing + colorbar + safety

**Files:**
- Modify: `src/mcp/plot_renderer/tools/render_map.py`
- Create: `tests/mcp/plot_renderer/unit/test_render_map.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_render_map.py
import pytest

from src.mcp.plot_renderer.tools import render_map as rm

if not rm._CARTOPY_OK:  # pragma: no cover
    pytest.skip("cartopy not installed; run map tests in maps-extra env",
                allow_module_level=True)


def test_basic_map_renders(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "title": "demo",
        "colormap": "viridis",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    out = env["result"]
    assert out["output_path"].endswith(".png")
    assert out["file_size_bytes"] > 5000
    drawn = out["oracle"]["drawn"]
    assert drawn["projection_class"] == "PlateCarree"
    assert drawn["coastlines_drawn"] is True
    assert drawn["title"] == "demo"


def test_explicit_projection_robinson(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "projection": "Robinson",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["projection_class"] == "Robinson"


def test_unknown_projection_returns_ambiguity(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "projection": "NotARealProjection",
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "unknown_projection"


def test_unknown_colormap_returns_ambiguity(tmp_path, monkeypatch, small_2d_dataset):
    monkeypatch.chdir(tmp_path)
    ds = small_2d_dataset
    spec = {
        "values": ds["v"].values.tolist(),
        "lat": ds["lat"].values.tolist(),
        "lon": ds["lon"].values.tolist(),
        "colormap": "NotARealCmap",
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "unknown_colormap"


def test_lon_shift_warning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {
        "values": [[1.0, 2.0, 3.0, 4.0]],
        "lat": [0.0],
        "lon": [180.0, 270.0, 0.0, 90.0],   # 0..360 layout
        "lon_convention": "-180..180",
    }
    env = rm.render_map(spec)
    assert env["ok"] is True
    codes = [w["code"] for w in env["warnings"]]
    assert "lon_shift_applied" in codes


def test_all_nan_returns_ambiguity(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {
        "values": [["NaN", "NaN"], ["NaN", "NaN"]],
        "lat": [0.0, 1.0],
        "lon": [0.0, 1.0],
    }
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["subcode"] == "all_nan"
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Replace `render_map.py` body with full implementation**

```python
# src/mcp/plot_renderer/tools/render_map.py
"""FORMAT-SPECIFIC (cartopy-aware): map rendering.

This is the only file in cycle-2 that imports cartopy. The seam test
allows it; other tools must not import cartopy.
"""
from __future__ import annotations

from typing import Any

import matplotlib.pyplot as plt
import numpy as np

from src.mcp.plot_renderer import (
    adapter, colormap_registry, defaults as _defaults,
    envelope, lifecycle, oracle, safety, style,
)
from src.mcp.plot_renderer.envelope import WarningCode

try:
    import cartopy.crs as ccrs  # type: ignore[import-not-found]
    import cartopy.feature as cfeature  # type: ignore[import-not-found]
    _CARTOPY_OK = True
    _CARTOPY_IMPORT_ERROR: str | None = None
except ImportError as e:
    ccrs = None  # type: ignore[assignment]
    cfeature = None  # type: ignore[assignment]
    _CARTOPY_OK = False
    _CARTOPY_IMPORT_ERROR = str(e)


_PROJECTION_CLASSES = (
    "PlateCarree", "Robinson", "NorthPolarStereo", "SouthPolarStereo",
    "LambertConformal", "Mercator",
)


def _cartopy_ambiguity() -> dict[str, Any]:
    return envelope.ambiguous(
        subcode="cartopy_missing",
        message=("cartopy is not installed. Install with "
                 "`uv pip install cartopy` (PROJ + GEOS C libs required) or "
                 "wait for cycle-5 auto-install."),
        candidates=[
            {"param": "install", "value": "uv pip install cartopy",
             "kind": "shell_command"},
            {"param": "install", "value": "conda install -c conda-forge cartopy",
             "kind": "shell_command"},
        ],
        retry_with_param=None,
        context={"import_error": _CARTOPY_IMPORT_ERROR},
    )


def _resolve_presentation(resolved: dict[str, Any]) -> dict[str, Any]:
    out = dict(resolved)
    for k, v in _defaults.LIBRARY_DEFAULTS.items():
        out.setdefault(k, v)
    return out


def _sources(spec: dict[str, Any], trace: dict[str, Any]) -> dict[str, str]:
    explicit = set(spec.keys())
    applied = set(trace.get("fields_applied", []))
    sources: dict[str, str] = {}
    for field in ("colormap", "projection", "colorbar_position",
                   "gridlines", "font_scale", "aspect"):
        if field in explicit and spec[field] is not None:
            sources[field] = "explicit"
        elif field in applied:
            sources[field] = "style_template"
        else:
            sources[field] = "library_default"
    return sources


def _make_projection(name: str):
    if name not in _PROJECTION_CLASSES:
        raise _UnknownProjection(name)
    return getattr(ccrs, name)()


class _UnknownProjection(ValueError):
    pass


def render_map(spec: dict[str, Any]) -> dict[str, Any]:
    """Render a 2D lat/lon map. See spec §2.1."""
    if not _CARTOPY_OK:
        return _cartopy_ambiguity()

    warnings: list[dict[str, Any]] = []
    try:
        # 1. Normalize spec → values, coords, meta
        try:
            values, coords, meta = adapter.normalize_2d_any_form(spec)
        except adapter.InvalidSpecError as e:
            return envelope.error("invalid_spec", str(e))

        if values.size == 0:
            return envelope.ambiguous(
                subcode="empty_slice",
                message="data array has zero cells",
                candidates=[{"param": "region", "value": "non-empty bbox"}],
                retry_with_param="region",
                context={"shape": list(values.shape)},
            )

        # 2. Style
        resolved, trace = style.apply(spec, spec.get("style_template"))
        resolved = _resolve_presentation(resolved)

        # 3. Validate cmap + projection names
        cmap_name = resolved.get("colormap", "viridis")
        if not colormap_registry.is_known_cmap(cmap_name):
            return envelope.ambiguous(
                subcode="unknown_colormap",
                message=f"unknown colormap: {cmap_name!r}",
                candidates=[{"param": "colormap", "value": "viridis"},
                            {"param": "colormap", "value": "RdBu_r"}],
                retry_with_param="colormap",
                context={"requested": cmap_name},
            )
        proj_name = resolved.get("projection", "PlateCarree")
        try:
            proj = _make_projection(proj_name)
        except _UnknownProjection:
            return envelope.ambiguous(
                subcode="unknown_projection",
                message=f"unknown projection: {proj_name!r}",
                candidates=[{"param": "projection", "value": p}
                            for p in _PROJECTION_CLASSES],
                retry_with_param="projection",
                context={"requested": proj_name},
            )

        # 4. Safety pass
        nan = safety.nan_assessment(values)
        if nan["all_nan"]:
            return envelope.ambiguous(
                subcode="all_nan",
                message="every cell is NaN; nothing to plot",
                candidates=[{"param": "region",
                             "value": "non-NaN spatial extent"},
                            {"param": "time", "value": "different time index"}],
                retry_with_param="region",
                context={"nan_fraction": 1.0},
            )
        if nan["high_nan_fraction"]:
            warnings.append(envelope.warn(
                WarningCode.HIGH_NAN_FRACTION,
                f"{nan['nan_fraction']:.0%} of cells are NaN",
                {"nan_fraction": nan["nan_fraction"]}))

        const, const_value = safety.is_constant_field(values)
        if const and const_value is not None:
            warnings.append(envelope.warn(
                WarningCode.CONSTANT_FIELD,
                "field has zero variation",
                {"value": const_value}))

        values, coords["lon"], lon_shifted = safety.maybe_lon_shift(
            values, coords["lon"], target=spec.get("lon_convention"))
        if lon_shifted:
            warnings.append(envelope.warn(
                WarningCode.LON_SHIFT_APPLIED,
                f"longitudes shifted to {spec['lon_convention']}",
                {"target": spec["lon_convention"]}))

        downsample_enabled = (resolved.get("downsample", True) is not False)
        values, coords, ds_action = safety.auto_downsample_2d(
            values, coords, enabled=downsample_enabled)
        if ds_action is not None:
            warnings.append(envelope.warn(
                WarningCode.AUTO_DOWNSAMPLED,
                f"downsampled {ds_action['from_shape']} → {ds_action['to_shape']}",
                ds_action))

        clip_pct = spec.get("clip_pct") or resolved.get("clip_pct")
        clip_pct_tuple = tuple(clip_pct) if clip_pct is not None else None
        vmin, vmax, clip_applied = safety.percentile_clip_if_extreme(
            values,
            vmin=spec.get("vmin"), vmax=spec.get("vmax"),
            clip_pct=clip_pct_tuple,
        )
        if clip_applied:
            warnings.append(envelope.warn(
                WarningCode.PERCENTILE_CLIP_APPLIED,
                f"applied percentile clip [{vmin:.3g}, {vmax:.3g}]",
                {"vmin": vmin, "vmax": vmax}))

        # 5. Render
        fig = plt.figure(figsize=(8.0, 5.0))
        ax = fig.add_subplot(1, 1, 1, projection=proj)
        cmap = plt.get_cmap(cmap_name).copy()
        cmap.set_bad(alpha=0.0)
        masked = np.ma.masked_invalid(values)
        mesh = ax.pcolormesh(
            coords["lon"], coords["lat"], masked,
            transform=ccrs.PlateCarree(),
            cmap=cmap, vmin=vmin, vmax=vmax, rasterized=True,
            shading="auto",
        )
        coastlines_drawn = False
        try:
            ax.add_feature(cfeature.COASTLINE, linewidth=0.5)
            coastlines_drawn = True
        except Exception:
            pass
        if resolved.get("gridlines") != "none":
            ax.gridlines(draw_labels=False, linewidth=0.3, alpha=0.4)
        cbar_pos = resolved.get("colorbar_position") or "right"
        if cbar_pos != "none":
            orientation = "horizontal" if cbar_pos in ("top", "bottom") else "vertical"
            cb = fig.colorbar(mesh, ax=ax, orientation=orientation, fraction=0.04, pad=0.04)
            if spec.get("colorbar_label"):
                cb.set_label(spec["colorbar_label"])
        if spec.get("title"):
            ax.set_title(spec["title"])
        extent = spec.get("extent")
        if extent:
            ax.set_extent(extent, crs=ccrs.PlateCarree())
        fig.tight_layout()

        # 6. Output
        fmt = resolved.get("format", "png")
        dpi = int(resolved.get("dpi", 150))
        lifecycle.validate_dpi(dpi)
        if spec.get("output_path"):
            try:
                output_path = lifecycle.resolve_output_path(
                    spec["output_path"], fmt=spec.get("format"))
            except lifecycle.FormatExtensionMismatch as e:
                plt.close(fig)
                return envelope.error("format_extension_mismatch", str(e))
            except lifecycle.UnsupportedFormat as e:
                plt.close(fig)
                return envelope.error("unsupported_format", str(e))
            except lifecycle.OutputPathInvalid as e:
                plt.close(fig)
                return envelope.error("output_path_invalid", str(e))
        else:
            output_path = lifecycle.auto_name(tool="map", spec=spec, fmt=fmt)
        try:
            size_bytes = lifecycle.atomic_save(fig, output_path, dpi=dpi)
        except OSError as e:
            plt.close(fig)
            return envelope.error("output_dir_unwritable", str(e))

        # 7. Oracle
        sa = {
            "plotted_min": float(np.nanmin(values)) if np.isfinite(values).any() else None,
            "plotted_max": float(np.nanmax(values)) if np.isfinite(values).any() else None,
            "nan_fraction": float(nan["nan_fraction"]),
            "applied_downsample": ds_action,
            "applied_lon_shift": lon_shifted,
            "applied_clip_pct": list(clip_pct) if (clip_applied and clip_pct) else
                                 ([2.0, 98.0] if clip_applied else None),
            "vmin_used": float(vmin),
            "vmax_used": float(vmax),
        }
        ocl = oracle.capture_common(
            fig=fig, tool="render_map",
            resolved_spec=resolved,
            style_resolution_sources=_sources(spec, trace),
            safety_actions=sa, output_path=output_path,
            output_size_bytes=size_bytes, data_shape=list(values.shape))
        ocl["drawn"] = oracle.drawn_for_map(
            fig=fig, ax=ax,
            projection_class=proj_name,
            extent=list(extent) if extent else None,
            coastlines_drawn=coastlines_drawn,
            colorbar_label=spec.get("colorbar_label"))
        ocl["style_template_applied"] = oracle.style_template_applied_block(
            template=spec.get("style_template"), trace=trace)
        oracle.finalize(ocl)
        plt.close(fig)

        return envelope.success({
            "output_path": output_path,
            "file_size_bytes": size_bytes,
            "plotted_min": sa["plotted_min"],
            "plotted_max": sa["plotted_max"],
            "plotted_shape": list(values.shape),
            "applied_downsample": ds_action,
            "applied_lon_shift": lon_shifted,
            "nan_fraction": sa["nan_fraction"],
            "oracle": ocl,
        }, warnings=warnings)

    except Exception as e:
        return envelope.error("internal_render_error",
                              f"{type(e).__name__}: {e}")
```

- [ ] **Step 4: Run, verify green**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_render_map.py \
                 tests/mcp/plot_renderer/unit/test_render_map_no_cartopy.py -v
```

Expected: 6 + 1 = 7 passed (test_render_map.py auto-skips if cartopy not installed).

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/tools/render_map.py \
        tests/mcp/plot_renderer/unit/test_render_map.py
git commit -m "cycle-2 task 30: render_map full drawing path (projection + safety + oracle)"
```

---

### Task 31: Phase-7 lint and typecheck gate

- [ ] **Step 1: Run ruff, mypy, plot_renderer tests**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer && \
.venv/bin/mypy src/mcp/plot_renderer && \
.venv/bin/pytest tests/mcp/plot_renderer -v
```

- [ ] **Step 2: Commit if any fixes**

```bash
git add -A && git commit -m "cycle-2 phase-7 gate: lint + typecheck clean"
```

---

## Phase 8: MCP server wiring

The server is a thin dispatcher over the 3 tools. Same shape as
cycle-1's `server.py`: `dispatch(name, args)` plus an MCP wrapper that
serializes results as TextContent.

### Task 32: `server.py` — dispatch + tool registration

**Files:**
- Create: `src/mcp/plot_renderer/server.py`
- Create: `tests/mcp/plot_renderer/unit/test_server_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/unit/test_server_dispatch.py
from src.mcp.plot_renderer.server import dispatch, list_tool_names


def test_list_tool_names():
    assert list_tool_names() == ["render_map", "render_timeseries", "render_profile"]


def test_dispatch_unknown_tool():
    env = dispatch("not_a_tool", {})
    assert env["ok"] is False
    assert env["error"]["code"] == "unknown_tool"


def test_dispatch_render_timeseries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    args = {"spec": {"values": [0.0, 1.0],
                      "time": ["2024-01-15", "2024-02-15"],
                      "label": "demo"}}
    env = dispatch("render_timeseries", args)
    assert env["ok"] is True


def test_dispatch_bad_args_returns_internal_error(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Missing 'spec' key — render_timeseries(spec) gets called with arg
    env = dispatch("render_timeseries", {"wrong": True})
    assert env["ok"] is False
    # Either "internal_render_error" (caught in render_*) or "invalid_spec".
    assert env["error"]["code"] in ("internal_render_error", "invalid_spec")
```

- [ ] **Step 2: Run, verify failure**

- [ ] **Step 3: Implement `server.py`**

```python
# src/mcp/plot_renderer/server.py
"""MCP server entry point. Thin dispatch over the 3 callable tools."""
from __future__ import annotations

import asyncio
from typing import Any

from src.mcp.plot_renderer import envelope
from src.mcp.plot_renderer.tools import (
    render_map as _map,
    render_profile as _profile,
    render_timeseries as _ts,
)

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    import mcp.types as types
except ImportError:  # pragma: no cover
    Server = None  # type: ignore[misc,assignment]
    stdio_server = None  # type: ignore[misc,assignment]
    types = None  # type: ignore[misc,assignment]


def list_tool_names() -> list[str]:
    return ["render_map", "render_timeseries", "render_profile"]


def dispatch(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Internal dispatcher used by the MCP wrapper and by tests."""
    spec = args.get("spec", args) if isinstance(args, dict) else {}
    try:
        if name == "render_map":
            return _map.render_map(spec)
        if name == "render_timeseries":
            return _ts.render_timeseries(spec)
        if name == "render_profile":
            return _profile.render_profile(spec)
        return envelope.error(
            "unknown_tool",
            f"unknown tool: {name}",
            context={"name": name, "available": list_tool_names()})
    except TypeError as e:
        return envelope.error(
            "internal_render_error",
            f"bad arguments for {name}: {e}",
            context={"args": list(args.keys()) if isinstance(args, dict) else []})


def make_server() -> "Server":
    if Server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")
    server = Server("plot-renderer")

    @server.list_tools()  # type: ignore[misc]
    async def _list_tools() -> list[Any]:
        return [
            types.Tool(name=n, description=f"plot-renderer.{n}",
                       inputSchema={"type": "object"})
            for n in list_tool_names()
        ]

    @server.call_tool()  # type: ignore[misc]
    async def _call_tool(name: str, arguments: dict[str, Any]) -> Any:
        result = dispatch(name, arguments or {})
        import json
        return [types.TextContent(type="text", text=json.dumps(result, default=str))]

    return server


def main() -> None:
    if stdio_server is None:
        raise RuntimeError("mcp package not installed; install with [mcp] extra")
    server = make_server()

    async def _run() -> None:
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run, verify green**

Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/mcp/plot_renderer/server.py \
        tests/mcp/plot_renderer/unit/test_server_dispatch.py
git commit -m "cycle-2 task 32: MCP server dispatch + tool registration"
```

---

### Task 33: Phase-8 lint and typecheck gate

- [ ] **Step 1: Run ruff, mypy, plot_renderer tests**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer && \
.venv/bin/mypy src/mcp/plot_renderer && \
.venv/bin/pytest tests/mcp/plot_renderer -v
```

- [ ] **Step 2: Commit if any fixes**

```bash
git add -A && git commit -m "cycle-2 phase-8 gate: lint + typecheck clean"
```

---

## Phase 9: Seam test + extraction-prompt doc + README

### Task 34: Seam-discipline test

**Files:**
- Create: `tests/mcp/plot_renderer/unit/test_seam.py`

- [ ] **Step 1: Write the test**

```python
# tests/mcp/plot_renderer/unit/test_seam.py
"""Enforce the format-agnostic + cartopy-isolation seam discipline.

Files marked ⤴ format-agnostic must NOT import:
- NetCDF / HDF5 / Zarr / GRIB libraries (input formats)
- The cycle-1 package (loose coupling rule)

Only `slice_loader.py` (which sets __format_specific__ = True) may
import h5netcdf / netCDF4 / xarray's NetCDF engine paths.

Only `tools/render_map.py` may import cartopy.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest


_FORMAT_BANNED = {"netCDF4", "h5netcdf", "cftime", "pynio", "cfgrib", "zarr"}
_CYCLE1_BANNED = "src.mcp.netcdf_reader"
_CARTOPY_NAMES = {"cartopy", "cartopy.crs", "cartopy.feature"}

_PACKAGE_ROOT = Path(__file__).resolve().parents[4] / "src" / "mcp" / "plot_renderer"


def _python_files() -> list[Path]:
    return sorted(p for p in _PACKAGE_ROOT.rglob("*.py")
                  if "__pycache__" not in p.parts)


def _is_format_specific_module(path: Path) -> bool:
    src = path.read_text()
    return "__format_specific__ = True" in src


def _is_cartopy_aware_module(path: Path) -> bool:
    return path.name == "render_map.py"


def _imports_in(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(), filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                out.add(n.name.split(".")[0])
                out.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module.split(".")[0])
                out.add(node.module)
    return out


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_format_agnostic_no_format_imports(path: Path) -> None:
    if _is_format_specific_module(path):
        pytest.skip("format-specific module — exempt")
    imports = _imports_in(path)
    banned_hits = imports & _FORMAT_BANNED
    assert not banned_hits, (
        f"{path.name} (format-agnostic) imports format-specific libs: "
        f"{sorted(banned_hits)}")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_no_cycle1_import(path: Path) -> None:
    imports = _imports_in(path)
    for imp in imports:
        assert _CYCLE1_BANNED not in imp, (
            f"{path.name} imports cycle-1's package: {imp}; "
            f"contracts must be JSON shapes only")


@pytest.mark.parametrize("path", _python_files(), ids=lambda p: p.name)
def test_cartopy_isolation(path: Path) -> None:
    if _is_cartopy_aware_module(path):
        return
    imports = _imports_in(path)
    cartopy_hits = imports & _CARTOPY_NAMES
    assert not cartopy_hits, (
        f"{path.name} imports cartopy outside tools/render_map.py: "
        f"{sorted(cartopy_hits)}")
```

- [ ] **Step 2: Run, verify it passes (the discipline should already hold)**

```
.venv/bin/pytest tests/mcp/plot_renderer/unit/test_seam.py -v
```

Expected: all parametrized cases pass. If any fail, fix the offending file rather than relaxing the test.

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/plot_renderer/unit/test_seam.py
git commit -m "cycle-2 task 34: seam-discipline test (format-agnostic + cartopy isolation)"
```

---

### Task 35: Style-template extraction prompt doc

**Files:**
- Create: `docs/style_template_extraction_prompt.md`

- [ ] **Step 1: Write the doc**

Create `docs/style_template_extraction_prompt.md` with the following content. This is the contract cycle-3 skills will use to drive a vision LLM.

```markdown
# Style Template Extraction Prompt

This document defines the prompt template a vision-capable agent (Claude
Code, Claude Desktop, etc.) uses to extract a `style_template` JSON from
a user-provided reference plot image. The cycle-2 `plot-renderer` MCP
applies the resulting JSON deterministically.

## Schema (cycle-2 contract)

```json
{
  "colormap_kind": "sequential | diverging | categorical | null",
  "colormap_name": "<matplotlib name> | null",
  "vcenter": "<number> | null",
  "clip_pct": "[low, high] | null",

  "projection_family": "plate_carree | robinson | polar_stereo_north | polar_stereo_south | lambert_conformal | mercator | null",
  "extent_hint": "global | hemispheric | regional | null",

  "colorbar_position": "right | bottom | top | left | none | null",
  "legend_placement":  "best | outside_right | outside_bottom | none | null",
  "gridlines":         "none | light | heavy | null",
  "aspect":            "<number> | auto | null",
  "font_scale":        "<number 0.7..1.5> | null",

  "title_placement":   "top | none | null",
  "label_density":     "minimal | normal | verbose | null",

  "source": {
    "image_path": "<path or URL> | null",
    "extracted_by": "<model name> | null",
    "extracted_at": "<ISO timestamp> | null",
    "confidence":   "<float 0..1> | null"
  }
}
```

All fields are optional. If a field cannot be inferred with reasonable
confidence, set it to `null` and lower the overall `confidence` value.

## Extraction guidance

**colormap_kind**: Look at the colorbar (if present) and the data range.
- Smoothly varying single-hue or perceptually uniform → `sequential` (e.g. viridis, inferno)
- Symmetric around a midpoint, two-hue diverging palette → `diverging` (e.g. RdBu_r)
- Discrete blocks of unrelated colors → `categorical` (e.g. tab10)

**colormap_name**: Set only if the palette is unambiguously a known
matplotlib colormap. Otherwise leave `null` and let `colormap_kind`
drive the default selection. Common identifiable cmaps: `viridis`,
`inferno`, `plasma`, `magma`, `RdBu_r`, `RdYlBu_r`, `BrBG`, `coolwarm`,
`tab10`, `tab20`.

**vcenter**: For diverging cmaps, the value at which the central
neutral hue sits. Most commonly `0.0` (anomalies). Read the colorbar
tick labels.

**clip_pct**: If the colorbar visibly clips outliers (e.g. sharp
saturation at one or both ends), guess `[2, 98]`; if not visible, leave
`null`.

**projection_family**: Coastline shape inference.
- Straight horizontal/vertical gridlines, rectangle frame → `plate_carree`
- Curved gridlines, oval frame → `robinson`
- Polar circular frame, north hemisphere visible → `polar_stereo_north`
- Polar circular frame, south hemisphere visible → `polar_stereo_south`
- Conic, mid-latitude regional view → `lambert_conformal`
- Cylindrical with characteristic Mercator north-south stretch → `mercator`

**extent_hint**:
- `global` — full earth visible
- `hemispheric` — single hemisphere or large quadrant
- `regional` — single basin, country, continent

**colorbar_position**: Read from layout. Common: `right` for vertical
maps, `bottom` for landscape figures.

**legend_placement**: Time series / profile plots usually have legends.
- Inside the axes, lower-right or upper-right → `best`
- Outside the right edge → `outside_right`
- Outside the bottom → `outside_bottom`
- Absent → `none`

**gridlines**:
- No grid → `none`
- Faint grid → `light`
- Bold/heavy grid → `heavy`

**aspect**: For maps and rectangular plots, estimate width-to-height
ratio. For "natural" aspect (cartopy-default for the projection),
use `auto`.

**font_scale**: 1.0 is matplotlib default. Larger labels/titles → 1.2.
Tighter, smaller labels → 0.8.

**title_placement**: Almost always `top` if a title is visible.

**label_density**:
- Minimal axis labels and ticks → `minimal`
- Standard → `normal`
- Heavy annotation, multiple legends, callouts → `verbose`

## Confidence calibration

Set `source.confidence` based on how certain the extraction is:

- 0.9–1.0: All major fields inferable; reference image is clear, high-resolution, well-labeled.
- 0.7–0.9: Most fields confident; one or two ambiguous (e.g., colormap kind clear but exact name uncertain).
- 0.5–0.7: Some fields confident, others uncertain; reference image is small or low-contrast.
- < 0.5: Extraction is mostly guessing; consider returning very few fields and letting the renderer fall back to defaults.

## Example

**Reference image**: a global SST anomaly map with a horizontal
RdBu_r colorbar at the bottom, light gridlines, Robinson projection.

**Expected JSON**:

```json
{
  "colormap_kind": "diverging",
  "colormap_name": "RdBu_r",
  "vcenter": 0.0,
  "projection_family": "robinson",
  "extent_hint": "global",
  "colorbar_position": "bottom",
  "gridlines": "light",
  "aspect": "auto",
  "font_scale": 1.0,
  "title_placement": "top",
  "label_density": "normal",
  "source": {
    "image_path": "/data/refs/sst_anomaly_2024.png",
    "extracted_by": "claude-opus-4-7",
    "extracted_at": "2026-05-07T14:30:00Z",
    "confidence": 0.92
  }
}
```

## Renderer behavior

The cycle-2 `plot-renderer` MCP applies this JSON deterministically:
- Explicit fields in the user's render spec **override** template fields
  ("explicit > template > library_default").
- Unknown fields are recorded in `oracle.style_template_applied.fields_ignored`
  but never error.
- The `source` block flows through untouched into the oracle, so cycle-3
  skill-refiner can audit which plots came from which references.

See `docs/specs/2026-05-07-cycle-2-plot-renderer.md` §8 for the full
mapping table from template fields to renderer spec fields.
```

- [ ] **Step 2: Verify file exists and references are correct**

```bash
ls docs/style_template_extraction_prompt.md
grep -c "colormap_kind" docs/style_template_extraction_prompt.md
```

Expected: file exists; multiple matches.

- [ ] **Step 3: Commit**

```bash
git add docs/style_template_extraction_prompt.md
git commit -m "cycle-2 task 35: style_template extraction-prompt doc for cycle-3 wiring"
```

---

### Task 36: Update README

**Files:**
- Modify: `src/mcp/plot_renderer/README.md`

- [ ] **Step 1: Replace README with up-to-date content**

```markdown
# plot-renderer MCP server

Renders matplotlib/cartopy figures from structured plot specs.
Doesn't know about NetCDF — pure rendering.

## Tools

### `render_map(spec)`

Render a 2D lat/lon map. See spec §2.1 for full field list.

Key spec fields: `values + lat + lon` (inline) OR `slice_ref` (file
form), `projection`, `colormap`, `vmin/vmax/clip_pct`, `vcenter`,
`title`, `colorbar_label`, `lon_convention`, `style_template`,
`output_path`, `dpi`, `format`, `downsample`.

Returns: `{output_path, file_size_bytes, plotted_min, plotted_max,
plotted_shape, applied_downsample, applied_lon_shift, nan_fraction,
oracle}`.

Ambiguity envelopes: `cartopy_missing`, `unknown_colormap`,
`unknown_projection`, `empty_slice`, `all_nan`.

### `render_timeseries(spec)`

1D time series, single or multi (`series=[{values, time, label, color?}, ...]`).
Sugar `values+time` accepted for single-series. Optional `aggregation`,
`trendline` (`null|linear|lowess`), `style_template`. See spec §2.2.

### `render_profile(spec)`

Vertical profile. `series=[{values, vertical, label, color?}, ...]` plus
`vertical_units` (Pa/hPa/m/km), `vertical_axis` (x/y), `invert_pressure`,
`log_scale`. See spec §2.3.

## Envelope shape

Same as cycle-1's `netcdf-reader`:

```
{ok: true,  result: {...}, warnings: [...]}
{ok: false, error: {code, message, context}}
{ok: false, error: {code: "ambiguous", subcode, candidates, retry_with_param}}
```

## Output management

Figures default to `.ncplot/figures/{tool}_{var}_{when}_{hash6}.{format}`
unless `output_path` is supplied. Figures are persistent; the directory
is never auto-cleaned.

## Style by reference

Pass `style_template` (a JSON dict per spec §8) to apply look-and-feel
from a reference plot. Cycle-3 skills supply the dict by asking the
host LLM to extract it from a user-supplied image; cycle-2 stays
deterministic. See `docs/style_template_extraction_prompt.md`.

## Install

```bash
uv pip install -e src/mcp/plot_renderer
# Optional:
uv pip install cartopy   # for render_map
uv pip install scipy     # for trendline=lowess
```

## Implementation status

Implemented per `docs/plans/2026-05-07-cycle-2-plot-renderer.md`. Full
test suite under `tests/mcp/plot_renderer/`. Image-diff suite is
opt-in (`pytest --image-diff`).
```

- [ ] **Step 2: Verify**

```bash
grep -c "render_map" src/mcp/plot_renderer/README.md
```

Expected: multiple matches.

- [ ] **Step 3: Commit**

```bash
git add src/mcp/plot_renderer/README.md
git commit -m "cycle-2 task 36: README update — tool list, envelope, install"
```

---

## Phase 10: Integration tests

Phase 10 wires the tools end-to-end against real-shaped synthetic
data, plus the optional image-diff and real-files scaffolds.

### Task 37: Inline-form pipeline e2e

**Files:**
- Create: `tests/mcp/plot_renderer/integration/__init__.py`
- Create: `tests/mcp/plot_renderer/integration/test_pipeline_inline.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/integration/test_pipeline_inline.py
"""End-to-end inline-form pipeline: spec → render → PNG + oracle."""
import json
from pathlib import Path

import numpy as np
import pytest

from src.mcp.plot_renderer.tools import render_map as rm
from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries
from src.mcp.plot_renderer.tools.render_profile import render_profile


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_inline_map_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    lat = np.linspace(-30, 30, 7).tolist()
    lon = np.linspace(-60, 60, 13).tolist()
    values = (np.outer(np.cos(np.deg2rad(lat)),
                        np.sin(np.deg2rad(lon))) * 10.0).tolist()
    spec = {"values": values, "lat": lat, "lon": lon,
            "title": "demo", "colormap": "viridis",
            "output_path": str(tmp_path / "map.png")}
    env = rm.render_map(spec)
    assert env["ok"] is True
    out = env["result"]
    assert Path(out["output_path"]).exists()
    assert out["file_size_bytes"] > 5000
    assert out["oracle"]["tool"] == "render_map"
    assert out["oracle"]["drawn"]["projection_class"] == "PlateCarree"


def test_inline_timeseries_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [1.0, 2.0, 3.0],
            "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
            "label": "demo",
            "title": "Annual", "trendline": "linear"}
    env = render_timeseries(spec)
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).exists()
    assert env["result"]["oracle"]["drawn"]["trendline_present"] is True


def test_inline_profile_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"values": [288.0, 250.0, 220.0],
            "vertical": [1000.0, 500.0, 100.0],
            "vertical_units": "hPa", "title": "T(p)"}
    env = render_profile(spec)
    assert env["ok"] is True
    assert env["result"]["oracle"]["drawn"]["log_scale"] is True


def test_oracle_sidecar_when_requested(tmp_path, monkeypatch):
    """write_oracle_sidecar is documented in spec §5.5 — defer the
    sidecar implementation: this is a follow-up if needed.
    """
    monkeypatch.chdir(tmp_path)
    # Even without sidecar implementation, the oracle is in result.
    spec = {"values": [1.0, 2.0],
            "time": ["2024-01-15", "2024-02-15"]}
    env = render_timeseries(spec)
    assert "oracle" in env["result"]
```

- [ ] **Step 2: Run, verify failure (or pass — depends on whether `__init__.py` exists)**

If the test fails due to missing `__init__.py`:

```bash
touch tests/mcp/plot_renderer/integration/__init__.py
.venv/bin/pytest tests/mcp/plot_renderer/integration -v
```

Expected: 4 passed (or 3 + 1 skipped if cartopy missing).

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/plot_renderer/integration/__init__.py \
        tests/mcp/plot_renderer/integration/test_pipeline_inline.py
git commit -m "cycle-2 task 37: inline-form integration tests"
```

---

### Task 38: Slice-ref pipeline e2e (cross-MCP contract)

**Files:**
- Create: `tests/mcp/plot_renderer/integration/test_pipeline_slice_ref.py`

This test writes a NetCDF slice file shaped exactly like cycle-1's
`read_slice` file-form output, then renders it. It is the cross-cycle
regression test for the slice-file contract (spec §3.3).

- [ ] **Step 1: Write the failing test**

```python
# tests/mcp/plot_renderer/integration/test_pipeline_slice_ref.py
"""End-to-end slice_ref form pipeline.

The slice file format is the cross-MCP contract; if cycle-1 changes
how it writes slice files, this test catches the drift.
"""
from pathlib import Path

import numpy as np
import pytest
import xarray as xr

from src.mcp.plot_renderer.tools import render_map as rm


def _write_cf_slice(path: Path, *, curvilinear: bool = False) -> None:
    if not curvilinear:
        lat = np.linspace(-30, 30, 8).astype("f4")
        lon = np.linspace(-60, 60, 12).astype("f4")
        values = np.outer(np.cos(np.deg2rad(lat)),
                           np.sin(np.deg2rad(lon))).astype("f4")
        ds = xr.Dataset(
            {"tos": (("lat", "lon"), values,
                     {"units": "K", "long_name": "sea surface temperature",
                      "standard_name": "sea_surface_temperature"})},
            coords={"lat": ("lat", lat, {"units": "degrees_north"}),
                    "lon": ("lon", lon, {"units": "degrees_east"})},
            attrs={"Conventions": "CF-1.7"},
        )
    else:
        # Mock WRF-style 2D coords (curvilinear)
        ny, nx = 6, 9
        xlat = np.tile(np.linspace(-30, 30, ny).reshape(ny, 1), (1, nx))
        xlon = np.tile(np.linspace(-60, 60, nx).reshape(1, nx), (ny, 1))
        values = np.cos(np.deg2rad(xlat)) * np.sin(np.deg2rad(xlon))
        values = values.astype("f4")
        ds = xr.Dataset(
            {"tos": (("y", "x"), values, {"units": "K"})},
            coords={"xlat": (("y", "x"), xlat),
                    "xlon": (("y", "x"), xlon),
                    "y": np.arange(ny),
                    "x": np.arange(nx)},
            attrs={"Conventions": "CF-1.7"},
        )
    ds.to_netcdf(path, engine="h5netcdf")


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_rectilinear_slice_ref_e2e(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "slice.nc"
    _write_cf_slice(p, curvilinear=False)
    spec = {"slice_ref": {"path": str(p), "format": "netcdf",
                            "variable": "tos"},
            "output_path": str(tmp_path / "from_slice.png"),
            "title": "from slice"}
    env = rm.render_map(spec)
    assert env["ok"] is True, env.get("error")
    assert (tmp_path / "from_slice.png").exists()


def test_missing_variable_returns_invalid_spec(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    p = tmp_path / "slice.nc"
    _write_cf_slice(p)
    spec = {"slice_ref": {"path": str(p), "format": "netcdf",
                            "variable": "does_not_exist"}}
    if rm._CARTOPY_OK:
        env = rm.render_map(spec)
        assert env["ok"] is False
        assert env["error"]["code"] == "invalid_spec"


def test_nonexistent_slice_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    spec = {"slice_ref": {"path": str(tmp_path / "no.nc"),
                            "format": "netcdf", "variable": "tos"}}
    if rm._CARTOPY_OK:
        env = rm.render_map(spec)
        assert env["ok"] is False
        assert env["error"]["code"] == "invalid_spec"
```

- [ ] **Step 2: Run, verify failure / fix discrepancies**

```bash
.venv/bin/pytest tests/mcp/plot_renderer/integration/test_pipeline_slice_ref.py -v
```

Expected: tests pass (or skip if cartopy missing).

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/plot_renderer/integration/test_pipeline_slice_ref.py
git commit -m "cycle-2 task 38: slice_ref integration tests (cross-MCP contract)"
```

---

### Task 39: Three-tools smoke test

**Files:**
- Create: `tests/mcp/plot_renderer/integration/test_three_tools_smoke.py`

- [ ] **Step 1: Write the test**

```python
# tests/mcp/plot_renderer/integration/test_three_tools_smoke.py
"""Smoke: each callable tool produces a non-empty figure."""
import os
from pathlib import Path

import pytest

from src.mcp.plot_renderer.server import dispatch
from src.mcp.plot_renderer.tools import render_map as rm


def test_smoke_timeseries(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_timeseries", {"spec": {
        "values": [1.0, 2.0, 3.0],
        "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
        "label": "x",
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 1000


def test_smoke_profile(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_profile", {"spec": {
        "values": [288.0, 250.0],
        "vertical": [1000.0, 500.0],
        "vertical_units": "hPa",
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 1000


@pytest.mark.skipif(not rm._CARTOPY_OK, reason="cartopy not installed")
def test_smoke_map(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    env = dispatch("render_map", {"spec": {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [0.0, 1.0],
    }})
    assert env["ok"] is True
    assert Path(env["result"]["output_path"]).stat().st_size > 5000
```

- [ ] **Step 2: Run, verify green**

- [ ] **Step 3: Commit**

```bash
git add tests/mcp/plot_renderer/integration/test_three_tools_smoke.py
git commit -m "cycle-2 task 39: three-tools smoke (server dispatch)"
```

---

### Task 40: Image-diff scaffold (gated)

**Files:**
- Create: `tests/mcp/plot_renderer/integration/test_image_diff_optional.py`
- Create: `tests/golden/.gitkeep` (empty placeholder; reference PNGs added during release reviews)
- Modify: `pyproject.toml` (top-level) — add `--image-diff` and `--regenerate-golden` pytest options

- [ ] **Step 1: Add pytest options to top-level `pyproject.toml`**

If a `[tool.pytest.ini_options]` section exists, add or extend:

```toml
[tool.pytest.ini_options]
pythonpath = ["."]
addopts = "-ra"
markers = [
    "image_diff: run only when --image-diff is passed",
]
```

Add to `tests/conftest.py` (top-level, not the plot_renderer one):

```python
# tests/conftest.py — add image-diff CLI option
def pytest_addoption(parser):
    parser.addoption("--image-diff", action="store_true", default=False,
                     help="Run image-diff suite against tests/golden/")
    parser.addoption("--regenerate-golden", action="store_true", default=False,
                     help="Regenerate golden PNGs (requires --image-diff)")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--image-diff"):
        return
    skip_image = __import__("pytest").mark.skip(reason="--image-diff not given")
    for item in items:
        if "image_diff" in item.keywords:
            item.add_marker(skip_image)
```

If a top-level `tests/conftest.py` already exists from cycle-1, append this block; do not overwrite.

- [ ] **Step 2: Write the failing test (skipped by default)**

```python
# tests/mcp/plot_renderer/integration/test_image_diff_optional.py
"""Optional image-diff suite. Gated on `pytest --image-diff`.

Compares freshly rendered figures against committed PNGs in tests/golden/
using SSIM (scikit-image). Tolerance: SSIM >= 0.95.
"""
from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.image_diff

GOLDEN_DIR = Path(__file__).resolve().parents[3] / "tests" / "golden"
SSIM_THRESHOLD = 0.95


def _ssim(a_path: Path, b_path: Path) -> float:
    from skimage import io
    from skimage.metrics import structural_similarity as ssim
    a = io.imread(str(a_path), as_gray=True)
    b = io.imread(str(b_path), as_gray=True)
    if a.shape != b.shape:
        return 0.0
    score, _ = ssim(a, b, full=True, data_range=1.0)
    return float(score)


def _compare_or_regenerate(request, fresh: Path, golden: Path) -> None:
    if request.config.getoption("--regenerate-golden"):
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_bytes(fresh.read_bytes())
        pytest.skip(f"regenerated {golden.name}")
    if not golden.exists():
        pytest.fail(f"golden {golden.name} missing; run with --regenerate-golden")
    score = _ssim(fresh, golden)
    assert score >= SSIM_THRESHOLD, (
        f"SSIM {score:.3f} below {SSIM_THRESHOLD} for {golden.name}")


def test_golden_basic_map(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools import render_map as rm
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed")
    spec = {"values": [[1.0, 2.0], [3.0, 4.0]],
            "lat": [0.0, 1.0], "lon": [0.0, 1.0],
            "projection": "Robinson",
            "output_path": str(tmp_path / "fresh.png")}
    env = rm.render_map(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "basic_map_robinson.png")


def test_golden_timeseries_two_series(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries
    spec = {"series": [
        {"values": [1.0, 2.0, 3.0], "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
         "label": "A"},
        {"values": [3.0, 2.0, 1.0], "time": ["2024-01-15", "2024-02-15", "2024-03-15"],
         "label": "B"},
    ], "trendline": "linear",
       "output_path": str(tmp_path / "fresh.png")}
    env = render_timeseries(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "timeseries_two_series.png")


def test_golden_profile_pressure(request, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from src.mcp.plot_renderer.tools.render_profile import render_profile
    spec = {"values": [288.0, 270.0, 250.0, 220.0, 200.0],
            "vertical": [1000.0, 700.0, 500.0, 250.0, 100.0],
            "vertical_units": "hPa",
            "output_path": str(tmp_path / "fresh.png")}
    env = render_profile(spec)
    assert env["ok"] is True
    _compare_or_regenerate(request,
                            tmp_path / "fresh.png",
                            GOLDEN_DIR / "profile_pressure.png")
```

- [ ] **Step 3: Verify it skips by default**

```bash
.venv/bin/pytest tests/mcp/plot_renderer/integration/test_image_diff_optional.py -v
```

Expected: 3 skipped (because `--image-diff` not given).

- [ ] **Step 4: Verify regenerate path works (creates initial goldens)**

```bash
mkdir -p tests/golden
touch tests/golden/.gitkeep
.venv/bin/pytest tests/mcp/plot_renderer/integration/test_image_diff_optional.py \
    --image-diff --regenerate-golden -v
ls tests/golden/
```

Expected: 3 PNGs created in `tests/golden/` (or 2 if cartopy missing). Three test SKIPs (regen path).

- [ ] **Step 5: Verify diff path passes**

```bash
.venv/bin/pytest tests/mcp/plot_renderer/integration/test_image_diff_optional.py --image-diff -v
```

Expected: tests pass (SSIM = 1.0 against just-regenerated goldens).

- [ ] **Step 6: Commit goldens + the test + conftest changes**

```bash
git add tests/golden tests/mcp/plot_renderer/integration/test_image_diff_optional.py \
        tests/conftest.py pyproject.toml
git commit -m "cycle-2 task 40: image-diff scaffold (gated --image-diff) + initial goldens"
```

---

## Phase 11: Real-files scaffold + final polish

### Task 41: Real-files integration scaffold (opt-in)

**Files:**
- Create: `tests/mcp/plot_renderer/integration/test_real_files.py`
- Create: `docs/REAL_FILES_SETUP.md`
- Modify: `.gitignore` (add `tests/integration/real_files.json`)

- [ ] **Step 1: Create the doc**

```markdown
# Real-files integration setup

The plot-renderer real-files scaffold is OFF by default. Enable with:

    export NCPLOT_REAL_FILES=1
    pytest tests/mcp/plot_renderer/integration/test_real_files.py -v

It reads slice paths from a developer-local config:
`tests/integration/real_files.json` (gitignored).

## Config shape

```json
{
  "cf_slice":   "/data/cmip/tos_2024-09.nc",
  "wrf_slice":  "/data/wrf/wrfout_2024-09-15.nc",
  "roms_slice": "/data/roms/his_2024-09.nc",
  "variable_cf":   "tos",
  "variable_wrf":  "T2",
  "variable_roms": "temp"
}
```

The scaffold drives `read_slice`-shaped specs (cycle-1 contract) into
each of the three render tools. Asserts: no exceptions, PNG > 50 KB,
oracle's `nan_fraction < 1.0`.
```

- [ ] **Step 2: Write the scaffold test**

```python
# tests/mcp/plot_renderer/integration/test_real_files.py
"""Optional real-files integration. Gated on `NCPLOT_REAL_FILES=1`.

Reads paths from tests/integration/real_files.json (gitignored) and
drives each render tool against actual files. See REAL_FILES_SETUP.md.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from src.mcp.plot_renderer.tools import render_map as rm
from src.mcp.plot_renderer.tools.render_profile import render_profile
from src.mcp.plot_renderer.tools.render_timeseries import render_timeseries

CONFIG = Path(__file__).resolve().parents[3] / "integration" / "real_files.json"

pytestmark = pytest.mark.skipif(
    os.environ.get("NCPLOT_REAL_FILES") != "1",
    reason="set NCPLOT_REAL_FILES=1 to enable real-files tests",
)


def _config() -> dict:
    if not CONFIG.exists():
        pytest.skip(f"missing config {CONFIG}")
    return json.loads(CONFIG.read_text())


def test_real_cf_slice_renders(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = _config()
    if not rm._CARTOPY_OK:
        pytest.skip("cartopy not installed")
    spec = {"slice_ref": {"path": cfg["cf_slice"], "format": "netcdf",
                            "variable": cfg["variable_cf"]},
            "output_path": str(tmp_path / "cf.png"),
            "title": "real CF"}
    env = rm.render_map(spec)
    assert env["ok"] is True, env.get("error")
    assert Path(env["result"]["output_path"]).stat().st_size > 50_000
    assert env["result"]["nan_fraction"] < 1.0
```

- [ ] **Step 3: Add `tests/integration/real_files.json` to `.gitignore`**

```bash
echo "tests/integration/real_files.json" >> .gitignore
```

(If `tests/integration/` doesn't exist yet from cycle-1, no `mkdir` is needed; the file lives only on developer machines.)

- [ ] **Step 4: Verify it skips by default**

```bash
.venv/bin/pytest tests/mcp/plot_renderer/integration/test_real_files.py -v
```

Expected: 1 skipped.

- [ ] **Step 5: Commit**

```bash
git add tests/mcp/plot_renderer/integration/test_real_files.py \
        docs/REAL_FILES_SETUP.md .gitignore
git commit -m "cycle-2 task 41: real-files integration scaffold (NCPLOT_REAL_FILES gated)"
```

---

### Task 42: Final lint + typecheck + full suite green

- [ ] **Step 1: Run ruff on everything**

```bash
.venv/bin/ruff check src/mcp/plot_renderer tests/mcp/plot_renderer
```

Expected: clean.

- [ ] **Step 2: Run mypy on cycle-2 sources**

```bash
.venv/bin/mypy src/mcp/plot_renderer
```

Expected: clean.

- [ ] **Step 3: Run the full plot_renderer test suite**

```bash
.venv/bin/pytest tests/mcp/plot_renderer -v
```

Expected: all unit + integration tests pass; image-diff and real-files SKIPped (as designed).

- [ ] **Step 4: Run the full repo test suite to confirm no cycle-1 regressions**

```bash
.venv/bin/pytest -v
```

Expected: cycle-1's existing tests still green.

- [ ] **Step 5: Commit any final fixes**

```bash
git add -A
git commit -m "cycle-2 final gate: full lint + typecheck + suite green"
```

- [ ] **Step 6: Push the branch**

```bash
git push -u origin cycle-2-plot-renderer
```

- [ ] **Step 7: Open PR**

```bash
gh pr create --base master --head cycle-2-plot-renderer \
  --title "Cycle 2: plot-renderer MCP — maps, time series, profiles + style template" \
  --body "$(cat <<'EOF'
## Summary

- New MCP server `plot-renderer` exposing 3 tools (`render_map`, `render_timeseries`, `render_profile`)
- Hybrid hand-off contract with cycle-1's `read_slice` (inline OR `slice_ref`)
- Render-oracle JSON sidecar for tests (asserts what was drawn, not pixels)
- Style-by-reference: deterministic `style_template` application + extraction-prompt doc for cycle 3
- Graceful cartopy degradation (ambiguity envelope when missing)
- Format-agnostic seam discipline + cartopy isolation (enforced by `test_seam.py`)

## Stats

- 42 plan tasks across 11 phases
- Tools: 3 callable + library defaults + safety pass + style template
- Tests: ~25 unit + 4 integration (incl. opt-in image-diff and real-files)
- Lint + typecheck clean

## What's NOT in this PR

- Cross-section / Hovmöller (small follow-up)
- Multi-panel composition
- Animation
- Land/ocean masking
- Cycle-3 skill wiring for vision-based style extraction

## Test plan

- [ ] `pytest tests/mcp/plot_renderer -v` (default suite green)
- [ ] `pytest --image-diff` (golden-set SSIM passes)
- [ ] Manual: render a CF map with explicit cmap; confirm oracle `style_resolution.colormap.source == "explicit"`
- [ ] Manual (with cycle-1): `read_slice` → `render_map` end-to-end via slice file

## References

- Spec: `docs/specs/2026-05-07-cycle-2-plot-renderer.md`
- Plan: `docs/plans/2026-05-07-cycle-2-plot-renderer.md`
- Style-template extraction prompt: `docs/style_template_extraction_prompt.md`
EOF
)"
```

- [ ] **Step 8: Confirm PR URL**

The `gh pr create` command will print a URL. Save it for review handoff.

---

## End of plan

42 tasks, 11 phases:

| Phase | Tasks | Theme |
|-------|-------|-------|
| 1 | 1–5 | Foundation: skeleton, envelope, defaults, colormap_registry |
| 2 | 6–10 | Adapter + slice_loader |
| 3 | 11–15 | Safety pass: downsample, NaN, lon-shift, constant, clip |
| 4 | 16–19 | Style template: schema, mapping, precedence, trace |
| 5 | 20–22 | Lifecycle: output_path, auto-name, atomic save |
| 6 | 23–25 | Oracle: schema + per-tool drawn hooks |
| 7 | 26–31 | Per-tool render: timeseries, profile, map (cartopy guard + drawing) |
| 8 | 32–33 | MCP server wiring |
| 9 | 34–36 | Seam test + extraction-prompt doc + README |
| 10 | 37–40 | Integration tests (incl. gated image-diff) |
| 11 | 41–42 | Real-files scaffold + final polish |

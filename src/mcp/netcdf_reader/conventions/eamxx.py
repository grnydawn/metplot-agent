"""Format-specific (NetCDF): E3SM EAMxx (SCREAM) detection.

EAMxx files typically declare `Conventions = CF-1.x` (so plain CF
detection fires) but their distinguishing feature is dual-grid
output: a physics column grid (`ncol`) AND a dycore spectral-element
grid (`elem × gp × gp`). Neither comes with `lat`/`lon` coordinate
variables in the data file — geometry lives in a separate scrip or
mapping file shared by every restart in the run.

Detection has to take precedence over plain CF so the convention
chain routes the file onto the unstructured branch rather than the
rectilinear branch (which would silently produce `spatial: null`,
as cycle-6 dogfooding observed).

Signals (in priority order):
  1. `source` attr matches "EAMxx" or "SCREAM" (strongest; what
     E3SM Atmosphere Model files reliably ship).
  2. `case` attr contains "SCREAM" (CIME run-name convention).
  3. Dim-shape corroboration (`ncol`, `elem`+`gp`).

The dycore-axis variables (`elem × gp × gp`) are detected here
but their plotting is deferred to cycle 10+ per cycle-9 spec §2;
the inspect path will surface them with a structured warning.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import xarray as xr

_EAMXX_SOURCE_RE = re.compile(r"EAMxx|SCREAM", re.IGNORECASE)
_EAMXX_CASE_RE = re.compile(r"SCREAM", re.IGNORECASE)


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []

    source = attrs.get("source", "")
    if isinstance(source, str) and _EAMXX_SOURCE_RE.search(source):
        evidence.append(f"source attr matches EAMxx/SCREAM ({source!r})")

    case = attrs.get("case", "")
    if isinstance(case, str) and _EAMXX_CASE_RE.search(case):
        evidence.append(f"case attr contains SCREAM ({case!r})")

    # Dim-shape corroboration. ncol = physics column axis;
    # elem + gp = dycore spectral-element axes. Either one,
    # combined with a source/case signal, raises confidence.
    has_ncol = "ncol" in ds.dims
    has_dycore = "elem" in ds.dims and "gp" in ds.dims
    if has_ncol:
        evidence.append(f"EAMxx physics axis present ('ncol'={ds.sizes['ncol']})")
    if has_dycore:
        evidence.append(
            f"EAMxx dycore axes present "
            f"('elem'={ds.sizes['elem']}, 'gp'={ds.sizes['gp']})")

    # We require AT LEAST one of the source/case attrs to fire,
    # otherwise we'd false-positive on any file shipping a generic
    # `ncol` dim (some non-EAMxx CF files use that name).
    has_attr_signal = any(
        e.startswith(("source attr", "case attr")) for e in evidence)
    if not has_attr_signal:
        return None

    # Confidence: attr + dim corroboration = high; attr alone = medium.
    if has_ncol or has_dycore:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "primary": "EAMxx",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def extract_spatial_eamxx(
    history_ds: xr.Dataset,
    grid_ds: xr.Dataset,
) -> dict[str, Any] | None:
    """Pair an EAMxx history with its physics-grid file and return
    the cycle-8 unstructured-mesh spatial envelope shape.

    EAMxx physics-grid files (SCRIP-style or simple lat/lon
    mapping) ship:
      - `lat[ncol]`, `lon[ncol]` (1-D cell centers, degrees)
      - Optionally `grid_corner_lat[ncol, ncorners]`,
        `grid_corner_lon[ncol, ncorners]` (SCRIP vertex bounds)

    Returns None if the grid file doesn't ship lat/lon on ncol.
    Dycore-axis variables (`elem × gp × gp`) are NOT covered here;
    those are surfaced as a separate warning at the inspect layer.
    """
    if "lat" not in grid_ds.variables or "lon" not in grid_ds.variables:
        return None
    if "ncol" not in grid_ds.dims:
        return None

    g_ncol = int(grid_ds.sizes["ncol"])

    # History must agree on ncol.
    if "ncol" in history_ds.dims:
        if int(history_ds.sizes["ncol"]) != g_ncol:
            return None

    # Shape sanity: lat/lon must be 1-D on ncol. SCRIP-style files
    # sometimes ship lat/lon as 2-D `(ncol, ncorners)` arrays — those
    # are vertex bounds, not centers. If we see those, we expect the
    # corresponding `grid_corner_*` variables to ship the bounds and
    # `lat`/`lon` to be 1-D centers; if `lat` is 2-D, the file is
    # SCRIP-with-bounds-only-no-centers and we can't proceed here.
    lat_da = grid_ds["lat"]
    lon_da = grid_ds["lon"]
    if lat_da.ndim != 1 or lon_da.ndim != 1:
        return None

    lat = np.asarray(lat_da.values, dtype=float)
    lon = np.asarray(lon_da.values, dtype=float)

    lon_min = float(np.nanmin(lon))
    lon_max = float(np.nanmax(lon))
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"

    has_vertex_bounds = (
        "grid_corner_lat" in grid_ds.variables
        and "grid_corner_lon" in grid_ds.variables)

    return {
        "coord_kind": "unstructured",
        "cell_dim": "ncol",
        "n_cells": g_ncol,
        "lat_var": "lat",
        "lon_var": "lon",
        "vertex_lat_var": "grid_corner_lat" if has_vertex_bounds else None,
        "vertex_lon_var": "grid_corner_lon" if has_vertex_bounds else None,
        "vertices_on_cell_var": None,  # SCRIP doesn't expose per-cell
                                       # vertex-index connectivity tables;
                                       # the corner arrays ARE the per-cell
                                       # vertices already.
        "lon_convention": lon_convention,
        "lat_range": [float(np.nanmin(lat)), float(np.nanmax(lat))],
        "lon_range": [lon_min, lon_max],
    }

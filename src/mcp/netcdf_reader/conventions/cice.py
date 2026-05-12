"""Format-specific (NetCDF): CICE5/6 sea-ice model detection.

CICE restart files ship no Conventions attr, no `source`, no
`model_name` — global attrs are typically a sparse {istep1, time,
nyr, month, mday, sec} block, none of which identify the producer.
Detection must therefore lean on the variable-name fingerprint.

The classic CICE5/6 variable suite covers:
  - Per-thickness-category thermodynamics: aicen, vicen, vsnon,
    Tsfcn, eicen, esnon, volpn, apondn, hpondn
  - Dynamics: uvel, vvel, stressp_1..4, stressm_1..4, stress12_1..4
  - Mask: iceumask

We require ≥3 fingerprint hits to detect. Single-name matches
(uvel, vvel alone) are common in other ocean / atmospheric codes
and would generate false positives. Three hits across the suite is
specific enough to be safe.

Spatial extraction is paired (cycle 9 spec §3.2): a CICE restart
alone has no coordinates. The geometry lives in a separate CICE
grid file (TLAT/TLON on `(nj, ni)`). The bare-restart case
generates the `mesh_pairing_required` ambiguous envelope in
inspect.py; the paired call dispatches to extract_spatial_cice
here.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

_CICE_FINGERPRINT_VARS = (
    # Per-category thermodynamic state
    "aicen", "vicen", "vsnon", "Tsfcn",
    "eicen", "esnon", "volpn", "apondn", "hpondn",
    # Dynamics
    "uvel", "vvel",
    "stressp_1", "stressp_2", "stressp_3", "stressp_4",
    "stressm_1", "stressm_2", "stressm_3", "stressm_4",
    "stress12_1", "stress12_2", "stress12_3", "stress12_4",
    # Mask
    "iceumask",
    # Radiation
    "swvdr", "swvdf", "swidr", "swidf",
    # Ocean coupling
    "strocnxT", "strocnyT",
)
_CICE_MIN_FINGERPRINT_HITS = 3


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    hits = [v for v in _CICE_FINGERPRINT_VARS if v in ds.data_vars]
    if len(hits) < _CICE_MIN_FINGERPRINT_HITS:
        return None

    evidence = [
        f"CICE variable fingerprint matched ({len(hits)} hits: "
        f"{', '.join(hits[:5])}"
        + (f", … +{len(hits) - 5} more" if len(hits) > 5 else "")
        + ")"
    ]
    # Optional secondary signal: CICE-shaped dim names.
    if "ncat" in ds.dims:
        evidence.append("CICE category dim present ('ncat')")
    if "nj" in ds.dims and "ni" in ds.dims:
        evidence.append(
            f"CICE horizontal dim pair present "
            f"('nj'={ds.sizes['nj']}, 'ni'={ds.sizes['ni']})")

    # Confidence ladder: 5+ hits = high; 3-4 hits = medium-high; the
    # threshold floor of 3 with the dim corroboration counts as high.
    has_dim_pair = "nj" in ds.dims and "ni" in ds.dims
    if len(hits) >= 5 or has_dim_pair:
        confidence = "high"
    else:
        confidence = "medium"

    return {
        "primary": "CICE",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def extract_spatial_cice(
    history_ds: xr.Dataset,
    grid_ds: xr.Dataset,
) -> dict[str, Any] | None:
    """Pair a CICE restart with its grid file and return the cycle-8
    unstructured-mesh spatial envelope shape.

    CICE grid files ship `TLAT(nj, ni)` and `TLON(nj, ni)` in degrees.
    Some restarts flatten the horizontal axis to `(nj=1, ni=N)`; the
    flattening must be reversed via the grid file's true `(nj, ni)`
    shape — if `history.nj * history.ni == grid.nj * grid.ni`, the
    history data is the flattened view and the grid's shape is the
    target.

    Returns None if the grid file doesn't ship TLAT/TLON.
    """
    if "TLAT" not in grid_ds.variables or "TLON" not in grid_ds.variables:
        return None
    if "nj" not in grid_ds.dims or "ni" not in grid_ds.dims:
        return None

    g_nj, g_ni = int(grid_ds.sizes["nj"]), int(grid_ds.sizes["ni"])
    n_cells = g_nj * g_ni

    # Validate the shapes are compatible (either matching directly,
    # or matching after flattening). We don't actually reshape the
    # history here — that happens at slice/render time — we only
    # validate the geometry pair makes sense.
    if "nj" in history_ds.dims and "ni" in history_ds.dims:
        h_nj, h_ni = (
            int(history_ds.sizes["nj"]), int(history_ds.sizes["ni"]))
        if h_nj * h_ni != n_cells:
            return None

    lat = np.asarray(grid_ds["TLAT"].values, dtype=float)
    lon = np.asarray(grid_ds["TLON"].values, dtype=float)

    lon_min = float(np.nanmin(lon))
    lon_max = float(np.nanmax(lon))
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"

    has_vertex_bounds = (
        "latt_bounds" in grid_ds.variables
        and "lont_bounds" in grid_ds.variables)

    return {
        "coord_kind": "unstructured",
        "cell_dim": "ni",
        "n_cells": n_cells,
        "lat_var": "TLAT",
        "lon_var": "TLON",
        "vertex_lat_var": "latt_bounds" if has_vertex_bounds else None,
        "vertex_lon_var": "lont_bounds" if has_vertex_bounds else None,
        "vertices_on_cell_var": None,  # CICE grids don't ship per-cell
                                       # vertex-index connectivity tables.
        "lon_convention": lon_convention,
        "lat_range": [float(np.nanmin(lat)), float(np.nanmax(lat))],
        "lon_range": [lon_min, lon_max],
        # CICE-specific: the grid is reshape-restorable to 2-D
        # (nj, ni). Renderer uses this hint to choose pcolormesh
        # over scatter when both are viable.
        "grid_shape_2d": [g_nj, g_ni],
    }

"""Format-specific (NetCDF): MPAS-aware detection.

MPAS (Model for Prediction Across Scales) is used by MPAS-Ocean,
MPAS-Atmosphere, MPAS-Seaice, the E3SM family, and Omega. All share the
same unstructured Voronoi-mesh layout: cells, edges, vertices.

Cycle-6 dogfooding surfaced two real shapes that detection must catch:

  - **Mesh files** (ocean_mesh.nc): ship Conventions='MPAS' plus
    core_name / model_name attrs and lowercase `nCells` / `nEdges`
    dims. The strong-signal case.

  - **History files** (ocn.hist.*.nc / Omega IOStreamsTest output):
    ship *no* Conventions attr, *no* core_name, and use **uppercase**
    `NCells` / `NEdges` / `NVertLayers` dim names. The dim fingerprint
    is the only signal.

Detection here covers both. Plotting / mesh-pairing / TEOS-10
vocabulary handling belongs in downstream skills (cycle 8 unstructured-
mesh work). This module returns convention identity only.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr

# MPAS canonical dim names, lowercased for case-insensitive matching.
# `nVertLayers` (Omega/MPAS-Ocean history) and `nVertLevels` (MPAS mesh)
# are both included — they vary by version of the codebase.
_MPAS_CELL_DIM_NAMES = ("ncells",)
_MPAS_EDGE_DIM_NAMES = ("nedges",)
_MPAS_VERTICAL_DIM_NAMES = ("nvertlevels", "nvertlayers")
_MPAS_COORD_VAR_NAMES = (
    "latCell", "lonCell", "xCell", "yCell", "zCell",
    "verticesOnCell", "cellsOnVertex", "nEdgesOnCell",
)
_MPAS_CORE_NAMES = ("ocean", "atmosphere", "seaice", "landice")


def _has_dim_ci(ds: xr.Dataset, candidates: tuple[str, ...]) -> str | None:
    """Return the actual dim name matching any of `candidates`
    (case-insensitive), or None."""
    lc = {str(d).lower(): str(d) for d in ds.dims}
    for c in candidates:
        if c in lc:
            return lc[c]
    return None


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    evidence: list[str] = []

    # Signal 1: explicit Conventions = "MPAS" (mesh files).
    conv = attrs.get("Conventions", "")
    if isinstance(conv, str) and "MPAS" in conv.upper():
        evidence.append(f"Conventions attr = {conv!r}")

    # Signal 2: model_name / source attrs identify the producer.
    for attr_name in ("model_name", "source"):
        v = attrs.get(attr_name, "")
        if isinstance(v, str) and "mpas" in v.lower():
            evidence.append(f"{attr_name} attr = {v!r}")

    # Signal 3: core_name is MPAS-specific terminology.
    core = attrs.get("core_name", "")
    if isinstance(core, str) and core.lower() in _MPAS_CORE_NAMES:
        evidence.append(f"core_name attr = {core!r}")

    # Signal 4: dim fingerprint. NCells + NEdges together is unique to
    # MPAS — no other convention we ship uses these names. The history
    # files (uppercase, no attrs) lean entirely on this.
    cell_dim = _has_dim_ci(ds, _MPAS_CELL_DIM_NAMES)
    edge_dim = _has_dim_ci(ds, _MPAS_EDGE_DIM_NAMES)
    if cell_dim and edge_dim:
        evidence.append(
            f"MPAS mesh dim pair present ({cell_dim!r}+{edge_dim!r})")
    elif cell_dim:
        # nCells alone is still suggestive (some MPAS subsets drop
        # edges) but weaker.
        evidence.append(f"MPAS cell dim present ({cell_dim!r})")

    # Signal 5: MPAS-style coordinate variables.
    coord_hits = [v for v in _MPAS_COORD_VAR_NAMES
                  if v in ds.data_vars or v in ds.coords]
    if coord_hits:
        evidence.append(
            f"MPAS coord variables present ({', '.join(coord_hits[:3])})")

    if not evidence:
        return None

    # Confidence ladder:
    # - Explicit Conventions/source attr OR (nCells + nEdges) → high
    # - Only nCells alone, or only coord vars → medium
    has_strong_attr = any(
        e.startswith(("Conventions attr", "model_name attr",
                      "source attr", "core_name attr"))
        for e in evidence
    )
    has_dim_pair = cell_dim is not None and edge_dim is not None
    has_coord_vars = bool(coord_hits)
    if has_strong_attr or has_dim_pair:
        confidence = "high"
    elif has_coord_vars or cell_dim:
        confidence = "medium"
    else:
        confidence = "low"

    return {
        "primary": "MPAS",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }


def _to_degrees_if_radians(arr: np.ndarray, attrs: dict[str, Any]
                            ) -> np.ndarray:
    """MPAS-Ocean ships latCell / lonCell in radians, often with no
    `units` attr (Phase A library-survey finding #1). Detect by units
    attr first, then by value range (lonCell in [0, 2π] fits inside
    |max| ≤ 2π+ε; real degree values would exceed that immediately).
    """
    units = ""
    raw = attrs.get("units")
    if isinstance(raw, str):
        units = raw.lower()
    if "radian" in units or units == "rad":
        return np.degrees(arr)
    if "degree" in units:
        return arr
    # No or ambiguous units — fall back to range detection.
    finite = arr[np.isfinite(arr)]
    if finite.size and float(np.abs(finite).max()) <= 2 * np.pi + 0.01:
        return np.degrees(arr)
    return arr


def extract_spatial_mpas(ds: xr.Dataset) -> dict[str, Any] | None:
    """Return the cycle-8 unstructured-mesh spatial envelope, or
    None if this file doesn't carry the canonical MPAS cell-centered
    geometry.

    Output shape (per cycle-8 spec §3.2):

        {
            "coord_kind": "unstructured",
            "cell_dim": "nCells",
            "n_cells": 7153,
            "lat_var": "latCell",
            "lon_var": "lonCell",
            "vertex_lat_var": "latVertex",
            "vertex_lon_var": "lonVertex",
            "vertices_on_cell_var": "verticesOnCell",
            "lon_convention": "0..360",
            "lat_range": [min, max],
            "lon_range": [min, max],
        }
    """
    cell_dim = _has_dim_ci(ds, _MPAS_CELL_DIM_NAMES)
    if cell_dim is None:
        return None
    if "latCell" not in ds.variables or "lonCell" not in ds.variables:
        # The history-file shape — coord vars live in the sibling mesh
        # file. The caller (inspect.py) should emit the
        # `mesh_pairing_required` ambiguous envelope for this case.
        return None

    lat = _to_degrees_if_radians(ds["latCell"].values, ds["latCell"].attrs)
    lon = _to_degrees_if_radians(ds["lonCell"].values, ds["lonCell"].attrs)

    lon_min = float(np.nanmin(lon))
    lon_max = float(np.nanmax(lon))
    if lon_min >= 0 and lon_max > 180:
        lon_convention = "0..360"
    elif lon_min < 0:
        lon_convention = "-180..180"
    else:
        lon_convention = "mixed"

    out: dict[str, Any] = {
        "coord_kind": "unstructured",
        "cell_dim": cell_dim,
        "n_cells": int(ds.sizes[cell_dim]),
        "lat_var": "latCell",
        "lon_var": "lonCell",
        "vertex_lat_var": (
            "latVertex" if "latVertex" in ds.variables else None),
        "vertex_lon_var": (
            "lonVertex" if "lonVertex" in ds.variables else None),
        "vertices_on_cell_var": (
            "verticesOnCell"
            if "verticesOnCell" in ds.variables else None),
        "lon_convention": lon_convention,
        "lat_range": [float(np.nanmin(lat)), float(np.nanmax(lat))],
        "lon_range": [lon_min, lon_max],
    }
    return out

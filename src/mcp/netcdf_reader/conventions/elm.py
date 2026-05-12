"""Format-specific (NetCDF): E3SM Land Model (ELM) detection.

ELM files come in two flavors:
  - elm.r.*   (restart): hierarchical dim mosaic
    `gridcell × topounit × landunit × column × pft` plus vertical
    `levgrnd`, `levlak`, `levsno`, `levcan`, `levsno1`, `levtot`.
  - elm.h*.*  (history) and elm.rh*.* (half-history): grid axis is
    `lndgrid` with `natpft` (natural PFTs) and `ltype` (land type).

Both flavors ship `source = "E3SM Land Model"`. Detection takes
precedence over plain CF because ELM files declare CF too.

Spatial extraction is deferred to cycle 11+ (PFT mosaic
visualization is its own visualization problem). Cycle 10 covers
detection-only.
"""
from __future__ import annotations

from typing import Any

import xarray as xr

_ELM_RESTART_DIMS = ("gridcell", "topounit", "landunit", "column", "pft")
_ELM_HISTORY_DIMS = ("lndgrid", "natpft", "ltype")
_ELM_SOURCE_RE = "e3sm land model"  # case-insensitive substring match


def detect(ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any] | None:
    # Signal 1: explicit source attr.
    source = attrs.get("source", "")
    has_source = (isinstance(source, str)
                   and _ELM_SOURCE_RE in source.lower())

    # Signal 2: dim fingerprint. ELM restart vs history shapes
    # are quite distinct, but at least one of the two mosaic
    # signatures should be present alongside the source attr.
    restart_hits = [d for d in _ELM_RESTART_DIMS if d in ds.dims]
    history_hits = [d for d in _ELM_HISTORY_DIMS if d in ds.dims]
    has_dim_fingerprint = len(restart_hits) >= 2 or len(history_hits) >= 2

    # Require the source attr to fire (the dim names alone aren't
    # specific enough to ELM — `gridcell` could show up in other
    # land models, and `pft` is generic plant-functional-type
    # terminology). The source attr is unambiguous.
    if not has_source:
        return None

    evidence: list[str] = [f"source attr = {source!r}"]
    if restart_hits:
        evidence.append(
            f"ELM restart dim fingerprint matched: "
            f"{', '.join(restart_hits)}")
    if history_hits:
        evidence.append(
            f"ELM history dim fingerprint matched: "
            f"{', '.join(history_hits)}")

    confidence = "high" if has_dim_fingerprint else "medium"

    return {
        "primary": "ELM",
        "confidence": confidence,
        "evidence": evidence,
        "candidates": None,
    }

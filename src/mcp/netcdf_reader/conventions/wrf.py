# src/mcp/netcdf_reader/conventions/wrf.py
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

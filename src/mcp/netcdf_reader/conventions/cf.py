# src/mcp/netcdf_reader/conventions/cf.py
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
        else:
            # No conventions attr and no soft signals — record uncertainty.
            candidates = [
                {"convention": "unknown", "confidence": 1.0, "evidence": []},
            ]

    return {
        "primary": primary,
        "confidence": confidence,
        "evidence": evidence,
        "candidates": candidates,
    }

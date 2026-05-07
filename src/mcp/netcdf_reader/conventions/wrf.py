# src/mcp/netcdf_reader/conventions/wrf.py
"""Format-specific (NetCDF): WRF-aware detection and helpers.
WRF is not CF-compliant; we surface it at inspect time so skills
and consumers can apply WRF-aware logic.
"""
from __future__ import annotations

from typing import Any

import numpy as np
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

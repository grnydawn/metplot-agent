# src/mcp/netcdf_reader/protocols.py
"""⤴ format-agnostic — eligible for _core/ lift.

Holds format-agnostic Protocol definitions that sit at the seam between
the cycle-1 NetCDF reader and a future _core/ package. The concrete
NetCDFAdapter lives in adapter.py (format-specific); this module names
the interface so format-agnostic callers (tools/*) can depend on it
without dragging adapter.py — and its NetCDF-specific machinery — into
their import graph.
"""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import xarray as xr


@runtime_checkable
class FormatAdapter(Protocol):
    name: str
    supported_schemes: set[str]

    def claims(self, path: str) -> bool: ...
    def expand(self, path: str) -> list[str]: ...
    def open(
        self,
        paths: list[str],
        file_objects: list[Any] | None = None,
        ssh_config: dict[str, Any] | None = None,
    ) -> xr.Dataset: ...
    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]: ...

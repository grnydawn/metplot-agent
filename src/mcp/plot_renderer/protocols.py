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

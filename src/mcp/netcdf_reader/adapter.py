# src/mcp/netcdf_reader/adapter.py
"""Format-specific: NetCDFAdapter implements the FormatAdapter protocol
that lives at the seam between cycle 1's reader and a future _core/
package. See spec §11."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import xarray as xr


@runtime_checkable
class FormatAdapter(Protocol):
    name: str
    supported_schemes: set[str]

    def claims(self, path: str) -> bool: ...
    def expand(self, path: str) -> list[str]: ...
    def open(self, paths: list[str], file_objects: list[Any] | None = None) -> xr.Dataset: ...
    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]: ...


class NetCDFAdapter:
    name = "netcdf"
    supported_schemes = {"file", "http", "https", "s3", "ssh"}

    _NC_SUFFIXES = (".nc", ".nc4", ".cdf")

    def claims(self, path: str) -> bool:
        # Heuristic: any path ending in .nc / .nc4 / .cdf, or any non-store scheme path
        # whose path component ends in those suffixes.
        lowered = path.lower()
        for s in self._NC_SUFFIXES:
            if lowered.endswith(s):
                return True
            # also handle "...?query" or fragment after suffix
            if s + "?" in lowered or s + "#" in lowered:
                return True
        return False

    def expand(self, path: str) -> list[str]:
        # Format-agnostic glob expansion handled in paths.classify.
        # NetCDF specifics live in paths.multi_file (Task 30+).
        return [path]

    def open(self, paths: list[str], file_objects: list[Any] | None = None) -> xr.Dataset:
        if file_objects:
            # One file_object per path; used by SSH path (later task).
            if len(file_objects) != 1:
                raise NotImplementedError("multi-file SSH not yet wired")
            return xr.open_dataset(file_objects[0], engine="h5netcdf",
                                   decode_times=True, chunks="auto")
        if len(paths) == 1:
            return xr.open_dataset(paths[0], decode_times=True, chunks="auto")
        # Multi-file path delegates to paths.multi_file (Task 31)
        from src.mcp.netcdf_reader.paths.multi_file import open_multi_file
        return open_multi_file(paths)

    def detect_conventions(self, ds: xr.Dataset, attrs: dict[str, Any]) -> dict[str, Any]:
        # CF detection lives in conventions/cf.py; WRF/ROMS in their own modules.
        # Wired here in Task 11+.
        from src.mcp.netcdf_reader.conventions import cf as _cf
        return _cf.detect(ds, attrs)

# src/mcp/plot_renderer/slice_loader.py
"""FORMAT-SPECIFIC: NetCDF SliceLoader.

This is the only file in cycle-2 that imports a NetCDF library. The
seam test reads __format_specific__ to skip it during the no-format
import audit.
"""
from __future__ import annotations

from typing import Any

import xarray as xr

__format_specific__ = True


class SliceFileUnreadable(Exception):
    pass


class NetCDFSliceLoader:
    name = "netcdf"
    supported_formats = {"netcdf"}

    def load(self, slice_ref: dict[str, Any]) -> xr.DataArray:
        fmt = slice_ref.get("format")
        if fmt not in self.supported_formats:
            raise SliceFileUnreadable(
                f"unsupported slice format: {fmt!r}; "
                f"this loader handles {sorted(self.supported_formats)}")
        path = slice_ref.get("path")
        var = slice_ref.get("variable")
        if not path:
            raise SliceFileUnreadable("slice_ref.path is missing or empty")
        if not var:
            raise SliceFileUnreadable("slice_ref.variable is missing or empty")
        try:
            ds = xr.open_dataset(path, engine="netcdf4",
                                 decode_times=True, chunks="auto")
        except FileNotFoundError as e:
            raise SliceFileUnreadable(f"file not found: {path}") from e
        except (OSError, ValueError) as e:
            raise SliceFileUnreadable(
                f"cannot open {path}: {type(e).__name__}: {e}") from e
        if var not in ds.data_vars:
            raise SliceFileUnreadable(
                f"variable {var!r} not found in {path}; "
                f"available: {sorted(ds.data_vars)}")
        return ds[var]

"""Format-specific (NetCDF): multi-file dataset opening with combine
fallback. Other formats (Zarr, GRIB) handle multi-file differently —
they keep their own paths/multi_file equivalents.
"""
from __future__ import annotations

import xarray as xr


class MultiFileCombineError(RuntimeError):
    pass


def _share_any_dim(paths: list[str]) -> bool:
    """Quick precheck: do all files share at least one common dim?
    Files with completely disjoint dim sets cannot be meaningfully combined.
    """
    dim_sets = []
    for p in paths:
        with xr.open_dataset(p, decode_times=False) as d:
            dim_sets.append(set(d.dims))
    if not dim_sets:
        return False
    common = dim_sets[0]
    for s in dim_sets[1:]:
        common = common & s
    return bool(common)


def open_multi_file(paths: list[str]) -> xr.Dataset:
    if not _share_any_dim(paths):
        raise MultiFileCombineError(
            f"could not combine {len(paths)} files: no shared dimensions"
        )
    try:
        return xr.open_mfdataset(paths, combine="by_coords",
                                 parallel=False, decode_times=True,
                                 chunks="auto", compat="override")
    except Exception as first_err:
        # Fallback: nested combine on most likely concat dim
        for concat_dim in ("time", "Time", "ocean_time"):
            try:
                return xr.open_mfdataset(
                    paths, combine="nested", concat_dim=concat_dim,
                    parallel=False, decode_times=True, chunks="auto",
                )
            except Exception:
                continue
        raise MultiFileCombineError(
            f"could not combine {len(paths)} files: {first_err!s}"
        )

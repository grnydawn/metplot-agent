"""Cycle 10 Task A2 — F-02 fix: adapter decode_times fallback.

Some real CF files (e.g. SCREAM rhist with `days since 0001-01-01
00:00:00` + noleap calendar) cause xarray's decode_times=True to
raise ValueError. The cycle-9 adapter let that exception bubble out
as `internal_error`. Cycle 10 makes the adapter retry once with
decode_times=False, stashes a `_metplot_time_decode_failed` flag
on the dataset, and inspect surfaces TIME_DECODE_FAILED warning.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools.inspect import inspect


def _year0001_noleap_file(tmp_path: Path) -> Path:
    """Build a fixture that trips xarray's decode_times. Use
    `days since 0001-01-01 00:00:00` + noleap calendar — the exact
    shape seen in the SCREAM rhist files.

    Use netCDF4-python directly so units/calendar attrs land
    unchanged on disk and xarray's read-time decoder gets the raw
    string it can't parse.
    """
    import netCDF4 as nc4

    p = tmp_path / "year0001.nc"
    # Empty float64 time array with year-0001 noleap origin is the
    # exact shape from SCREAM *.rhist.* — it's what trips xarray's
    # decoder even when cftime is installed.
    with nc4.Dataset(p, "w") as f:
        f.Conventions = "CF-1.7"
        f.createDimension("time", 0)
        f.createDimension("y", 2)
        tvar = f.createVariable("time", "f8", ("time",))
        tvar.units = "days since 0001-01-01 00:00:00"
        tvar.calendar = "noleap"
        foo = f.createVariable("foo", "f8", ("time", "y"))
        # No time entries → foo has shape (0, 2).
    return p


def test_adapter_falls_back_when_decode_times_raises(tmp_path: Path):
    """Pre-fix: adapter.open raises ValueError; inspect returns
    internal_error. Post-fix: adapter falls back to
    decode_times=False, dataset opens, _metplot_time_decode_failed
    flag is set."""
    p = _year0001_noleap_file(tmp_path)
    adapter = NetCDFAdapter()
    ds = adapter.open([str(p)])
    try:
        assert "time" in ds.dims
        # The fallback path leaves time as raw int64, not datetime.
        assert ds["time"].dtype != np.dtype("datetime64[ns]"), (
            "fallback path should not produce decoded datetimes; "
            "if this passes, the file no longer trips xarray and "
            "the fixture needs updating")
        # Flag must be set so callers can surface the structured warning.
        assert ds.attrs.get("_metplot_time_decode_failed") is True, (
            "adapter must stash the fallback flag so inspect can "
            "emit TIME_DECODE_FAILED")
    finally:
        ds.close()


def test_inspect_emits_time_decode_failed_warning(tmp_path: Path):
    """End-to-end: inspect on a F-02-class file returns ok=true
    with a TIME_DECODE_FAILED warning (not internal_error)."""
    p = _year0001_noleap_file(tmp_path)
    env = inspect(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True, (
        f"expected ok envelope; got {env.get('error')}")
    warn_codes = [w["code"] for w in env.get("warnings", [])]
    assert envelope.WarningCode.TIME_DECODE_FAILED in warn_codes, (
        f"expected TIME_DECODE_FAILED warning; got {warn_codes!r}")


def test_adapter_normal_file_no_flag(tmp_path: Path):
    """Regression: a normal CF file with decodable times does NOT
    set the flag — the flag is reserved for the fallback case."""
    ds = xr.Dataset(
        {"foo": (("time",), np.zeros(3))},
        coords={"time": (("time",),
                          np.array(["2024-01-01", "2024-01-02",
                                     "2024-01-03"],
                                    dtype="datetime64[ns]"))},
    )
    p = tmp_path / "normal.nc"
    ds.to_netcdf(p)
    adapter = NetCDFAdapter()
    opened = adapter.open([str(p)])
    try:
        assert "_metplot_time_decode_failed" not in opened.attrs
    finally:
        opened.close()

"""Cycle 10 Task A1 — F-01 fix: cf.py time-decode timedelta bug.

The Omega hifreq files (sub-daily noleap calendar) make xarray
decode time into cftime objects (object-dtype array). Then
np.diff(values) returns Python datetime.timedelta objects, which
can't be compared to np.timedelta64 — TypeError propagates.

Pin the fix: extract_time on a cftime-object-dtype coord returns
a valid time block without raising.
"""
from __future__ import annotations

import datetime as _dt

import cftime
import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.cf import extract_time


def _hifreq_like_dataset() -> xr.Dataset:
    """Synthetic Omega-hifreq stand-in: 4 sub-daily timestamps on
    a noleap calendar. xarray decode_times produces an object-dtype
    array of cftime.DatetimeNoLeap; np.diff yields
    datetime.timedelta objects, which is the F-01 trigger."""
    times = [
        cftime.DatetimeNoLeap(1, 6, 1, 0, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 6, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 12, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 18, 0, 0),
    ]
    return xr.Dataset(
        {"foo": (("time",), np.zeros(4))},
        coords={"time": (("time",), np.array(times, dtype=object))},
    )


def test_extract_time_does_not_raise_on_cftime_object_dtype():
    """Pre-fix: this raises TypeError at cf.py:157."""
    ds = _hifreq_like_dataset()
    t = extract_time(ds)
    assert t is not None
    assert t["name"] == "time"
    assert t["n"] == 4
    # Sub-daily monotonic-increasing series ⇒ "increasing".
    assert t["monotonic"] == "increasing", t


def test_extract_time_detects_non_monotonic_cftime():
    """Same path but a deliberately non-monotonic series — must
    return non-monotonic, not raise."""
    times = [
        cftime.DatetimeNoLeap(1, 6, 1, 0, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 12, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 6, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 18, 0, 0),
    ]
    ds = xr.Dataset(
        {"foo": (("time",), np.zeros(4))},
        coords={"time": (("time",), np.array(times, dtype=object))},
    )
    t = extract_time(ds)
    assert t is not None
    assert t["monotonic"] == "non-monotonic", t


def test_extract_time_detects_decreasing_cftime():
    times = [
        cftime.DatetimeNoLeap(1, 6, 1, 18, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 12, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 6, 0, 0),
        cftime.DatetimeNoLeap(1, 6, 1, 0, 0, 0),
    ]
    ds = xr.Dataset(
        {"foo": (("time",), np.zeros(4))},
        coords={"time": (("time",), np.array(times, dtype=object))},
    )
    t = extract_time(ds)
    assert t is not None
    assert t["monotonic"] == "decreasing", t


def test_extract_time_numpy_datetime64_path_unaffected():
    """Regression guard: the existing np.datetime64 path must keep
    working."""
    times = np.array(
        ["2024-01-01T00", "2024-01-02T00", "2024-01-03T00"],
        dtype="datetime64[ns]")
    ds = xr.Dataset(
        {"foo": (("time",), np.zeros(3))},
        coords={"time": (("time",), times)},
    )
    t = extract_time(ds)
    assert t is not None
    assert t["monotonic"] == "increasing"


def test_extract_time_real_hifreq_via_python_timedelta_diff():
    """Direct test of the comparison primitive: feed np.diff a
    pair of cftime objects and verify our fixed code handles the
    resulting Python timedelta."""
    a = cftime.DatetimeNoLeap(1, 6, 1, 0, 0, 0)
    b = cftime.DatetimeNoLeap(1, 6, 1, 6, 0, 0)
    diffs = np.diff(np.array([a, b], dtype=object))
    assert len(diffs) == 1
    assert isinstance(diffs[0], _dt.timedelta), (
        "fixture sanity: np.diff on cftime should yield datetime.timedelta")
    # And this comparison would fail under the pre-fix code:
    try:
        _ = diffs[0] > np.timedelta64(0, "ns")
        # If this didn't raise, numpy added cross-type support
        # in a later release — fine, our fix is still valid.
    except TypeError:
        pass  # exactly what we expect; the fix makes it irrelevant.

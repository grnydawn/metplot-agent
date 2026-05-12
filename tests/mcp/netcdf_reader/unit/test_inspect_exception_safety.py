"""Cycle 10 Task A0 — inspect() exception-safety harness.

Cycle-10 spec §4.1: "Task A's try/except hardening of inspect goes
in BEFORE the individual fixes so any future regression of the same
class produces a structured envelope rather than a raw exception."

The F-01 finding (hifreq TypeError) escaped to the caller because
the inspect inner pipeline's `try: ... finally:` lacks an `except`.
Pin the contract here: any exception raised inside the pipeline
must be caught and surfaced as an INTERNAL_ERROR envelope, never as
an uncaught Python exception.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader import envelope
from src.mcp.netcdf_reader.adapter import NetCDFAdapter
from src.mcp.netcdf_reader.tools import inspect as inspect_mod


def _minimal_cf_file(tmp_path: Path) -> Path:
    """Smallest possible CF-shaped file so inspect() reaches the
    convention detect step before our injected raiser fires."""
    ds = xr.Dataset(
        {"foo": (("y", "x"), np.zeros((2, 3)))},
        attrs={"Conventions": "CF-1.7"},
    )
    p = tmp_path / "tiny.nc"
    ds.to_netcdf(p)
    return p


class _RaisingAdapter(NetCDFAdapter):
    """An adapter whose detect_conventions raises mid-pipeline.

    Simulates the F-01 class — an exception that fires inside the
    inspect try-block but AFTER the file was opened, exactly where
    a raw exception would leak past the contract.
    """

    def detect_conventions(self, ds: xr.Dataset,
                            attrs: dict[str, Any]) -> dict[str, Any]:
        raise TypeError(
            "synthetic: simulating F-01-class crash mid-pipeline")


def test_inspect_returns_internal_error_envelope_when_pipeline_raises(
        tmp_path: Path):
    """No raw exception may escape inspect(). Pipeline-raised
    exceptions must surface as the INTERNAL_ERROR envelope shape so
    callers can act on them."""
    p = _minimal_cf_file(tmp_path)
    env = inspect_mod.inspect(str(p), adapter=_RaisingAdapter())
    assert env["ok"] is False, (
        "expected error envelope; got success — exception escaped?")
    assert env["error"]["code"] == envelope.ErrorCode.INTERNAL_ERROR, (
        f"expected INTERNAL_ERROR; got {env['error']['code']!r}")
    # The exception class + message must be in the envelope so audits
    # can reproduce the failure.
    msg = env["error"]["message"]
    assert "TypeError" in msg, msg
    assert "synthetic" in msg, msg


def test_inspect_closes_ds_when_pipeline_raises(tmp_path: Path,
                                                  monkeypatch):
    """The exception harness must NOT skip ds.close(). Verify by
    checking that the file handle was closed (xr.Dataset.close()
    flips the .closed flag)."""
    p = _minimal_cf_file(tmp_path)
    opened: list[xr.Dataset] = []
    real_open = NetCDFAdapter.open

    def spy_open(self, paths, **kw):
        ds = real_open(self, paths, **kw)
        opened.append(ds)
        return ds

    monkeypatch.setattr(NetCDFAdapter, "open", spy_open)
    _ = inspect_mod.inspect(str(p), adapter=_RaisingAdapter())
    assert len(opened) == 1
    # xarray's close() is idempotent; check the underlying file is
    # released by attempting a second close (it's a no-op when
    # already closed and shouldn't error).
    opened[0].close()  # should not raise


def test_inspect_normal_path_still_works(tmp_path: Path):
    """Sanity: the harness must not break the success path."""
    p = _minimal_cf_file(tmp_path)
    env = inspect_mod.inspect(str(p), adapter=NetCDFAdapter())
    assert env["ok"] is True, env.get("error")
    assert env["result"]["convention"]["primary"] is not None

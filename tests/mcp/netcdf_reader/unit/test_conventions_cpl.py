"""Cycle 10 Task D — F-07 CPL (E3SM coupler) detection.

CPL files ship coupler-internal mapping and history data with a
unique dim-name fingerprint:
  - Per-component domain: doma_n[xy], doml_n[xy], domo_n[xy],
    domi_n[xy] (atm/lnd/ocn/ice)
  - Component-to-coupler mapping axes: a2x_ax_n[xy], o2x_ox_n[xy],
    i2x_ix_n[xy], xao_ax_n[xy], etc. — the `[a-z]2[a-z]_[a-z]x_n[xy]`
    regex pattern uniquely identifies the coupler.

Detection-only in cycle 10 — most CPL variables are coupler-
internal mapping data, not user-plottable.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.cpl import detect


def _cpl_restart_like_dataset() -> xr.Dataset:
    """Match data/e3sm/cpl.r.* shape — uses real variable arrays
    so dims actually populate ds.dims."""
    return xr.Dataset(
        {
            "a2x_var": (("a2x_ax_ny", "a2x_ax_nx"),
                         np.zeros((1, 100))),
            "o2x_var": (("o2x_ox_ny", "o2x_ox_nx"),
                         np.zeros((1, 100))),
            "i2x_var": (("i2x_ix_ny", "i2x_ix_nx"),
                         np.zeros((1, 100))),
            "fractions": (("fractions_ax_ny", "fractions_ax_nx"),
                           np.zeros((1, 100))),
        }
    )


def _cpl_hi_like_dataset() -> xr.Dataset:
    """Match data/e3sm/cpl.hi.* shape (history)."""
    return xr.Dataset(
        {
            "doma_lat": (("doma_ny", "doma_nx"), np.zeros((1, 100))),
            "doml_lat": (("doml_ny", "doml_nx"), np.zeros((1, 100))),
            "domo_lat": (("domo_ny", "domo_nx"), np.zeros((1, 100))),
            "domi_lat": (("domi_ny", "domi_nx"), np.zeros((1, 100))),
        }
    )


def test_cpl_restart_detected():
    ds = _cpl_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "CPL"
    assert r["confidence"] == "high"


def test_cpl_hi_detected():
    ds = _cpl_hi_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "CPL"


def test_cpl_evidence_lists_dim_pattern_matches():
    ds = _cpl_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    ev = " ".join(r["evidence"]).lower()
    assert "a2x" in ev or "o2x" in ev or "i2x" in ev or "dom" in ev


def test_cpl_not_falsely_detected_on_generic_cf(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_cpl_not_falsely_detected_on_wrf(wrf_file):
    ds = xr.open_dataset(wrf_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_cpl_not_falsely_detected_on_one_a2x_dim_alone():
    """A file with a single coupler-style dim (no peer dims) is
    too weak to fire — could be an unrelated CIME-adjacent file."""
    ds = xr.Dataset(
        {"foo": (("a2x_ax_nx",), np.zeros(10))},
    )
    r = detect(ds, ds.attrs)
    assert r is None

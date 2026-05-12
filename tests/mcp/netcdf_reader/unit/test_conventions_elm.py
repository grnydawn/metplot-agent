"""Cycle 10 Task C2 — F-06 ELM (E3SM Land Model) detection.

Two real ELM file shapes:
  - elm.r.*    — restart: gridcell+topounit+landunit+column+pft
  - elm.h*/.rh0 — history: lndgrid+natpft+ltype

Both ship `source = "E3SM Land Model"`. Detection takes precedence
over plain CF (ELM files often declare CF-1.7 as well).
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.elm import detect


def _elm_restart_like_dataset() -> xr.Dataset:
    """Match data/e3sm/elm.r.* shape."""
    return xr.Dataset(
        {
            "timemgr_rst_type": (("scalar",), np.zeros(1)),
        },
        attrs={
            "Conventions": "CF-1.7",
            "source": "E3SM Land Model",
        },
    ).expand_dims({"gridcell": 12, "topounit": 12, "landunit": 30,
                    "column": 50, "pft": 100, "levsno": 5,
                    "levgrnd": 15})


def _elm_history_like_dataset() -> xr.Dataset:
    """Match data/e3sm/elm.rh0.* shape."""
    ds = xr.Dataset(
        {"T_SOIL_10CM": (("time", "lndgrid"), np.zeros((1, 10)))},
        attrs={
            "Conventions": "CF-1.7",
            "source": "E3SM Land Model",
            "case": "F2010-SCREAMv1.run.includes.eamxx",
        },
    )
    return ds.expand_dims({"natpft": 17, "ltype": 9})


def test_elm_detected_from_source_attr_and_dim_fingerprint():
    ds = _elm_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "ELM"
    assert r["confidence"] == "high"
    assert any("source" in e.lower() for e in r["evidence"]), r["evidence"]


def test_elm_history_flavor_detected():
    """elm.rh0 shape: source + lndgrid + natpft is enough."""
    ds = _elm_history_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "ELM"


def test_elm_source_only_without_dim_corroboration_still_detects():
    """Lone source attr is unambiguous — like EAMxx, it stands
    alone. Confidence may be lower without dim corroboration."""
    ds = xr.Dataset(
        {"foo": (("x",), np.zeros(3))},
        attrs={"source": "E3SM Land Model"},
    )
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "ELM"


def test_elm_dim_fingerprint_without_source_does_not_fire():
    """A file shipping `gridcell` and `pft` alone (no source attr)
    is suspicious but not confirmed — don't false-positive on
    non-ELM models that happen to share dim names."""
    ds = xr.Dataset(
        {"foo": (("gridcell", "pft"), np.zeros((3, 5)))},
    )
    r = detect(ds, ds.attrs)
    assert r is None


def test_elm_not_falsely_detected_on_generic_cf(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_elm_not_falsely_detected_on_wrf(wrf_file):
    ds = xr.open_dataset(wrf_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_elm_evidence_lists_source_and_dim_fingerprint():
    ds = _elm_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    ev = " ".join(r["evidence"]).lower()
    # Evidence should mention both the source attr and at least
    # one ELM-specific dim.
    assert "source" in ev
    assert any(d in ev for d in ("gridcell", "pft", "lndgrid"))

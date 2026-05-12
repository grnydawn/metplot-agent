"""Cycle 10 Task C1 — F-04 EAMxx detector tightening.

The cycle-9 detector treated `case` containing "SCREAM" as a
sufficient signal. Real elm.rh0 files ship
source = "E3SM Land Model" but a CIME `case` attr that includes
"SCREAM" (because the parent SCREAM coupled run produced them).
That false-positives the EAMxx detector and misroutes the file
to mesh-pair-prompt-for-EAMxx-scrip.

Fix: require dim corroboration (ncol OR elem+gp) when only `case`
matches. AND if `source` contains a clearly-different producer
("E3SM Land Model", "E3SM Sea Ice Model"), exit early.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.eamxx import detect


def test_no_false_positive_on_elm_rh0_shape():
    """Real ELM rh0 fixture shape: source = E3SM Land Model,
    case contains SCREAM, no ncol/elem/gp dims. Must NOT detect
    as EAMxx (the producer attr clearly says otherwise)."""
    ds = xr.Dataset(
        {
            "T_SOIL_10CM": (("time", "lndgrid"),
                             np.zeros((1, 10))),
        },
        attrs={
            "Conventions": "CF-1.7",
            "source": "E3SM Land Model",
            "case": "ERS_Ln22.ne30_ne30.F2010-SCREAMv1.frontier_craygnu-mphipcc.eamxx-internal_diagnostics_level--eamxx-output-preset-3.20260331_094847_9sd5hr",
        },
    )
    r = detect(ds, ds.attrs)
    assert r is None, (
        f"ELM rh0 with source=E3SM Land Model must NOT detect as "
        f"EAMxx (case-attr SCREAM-token is a CIME run-name "
        f"artifact); got {r!r}")


def test_no_false_positive_on_e3sm_sea_ice_model():
    """Same shape, different sibling producer — also must not fire."""
    ds = xr.Dataset(
        {"aicen": (("time", "ncat", "nj", "ni"),
                    np.zeros((1, 1, 1, 10)))},
        attrs={
            "source": "E3SM Sea Ice Model",
            "case": "F2010-SCREAMv1.run-name-includes-SCREAM",
        },
    )
    r = detect(ds, ds.attrs)
    assert r is None


def test_no_false_positive_on_case_alone_without_dim_corroboration():
    """A file with only `case` containing SCREAM but no source
    attr, no ncol/elem dims — too weak to fire."""
    ds = xr.Dataset(
        {"foo": (("x", "y"), np.zeros((3, 4)))},
        attrs={"case": "SCREAMv1.case.name"},
    )
    r = detect(ds, ds.attrs)
    assert r is None


def test_case_alone_plus_ncol_still_detects():
    """Real EAMxx physics-only restart where someone stripped
    `source` but `case` contains SCREAM AND ncol is present — the
    dim corroboration carries the signal."""
    ds = xr.Dataset(
        {"T_mid": (("time", "ncol", "lev"), np.zeros((1, 16, 8)))},
        attrs={"case": "F2010-SCREAMv1.run"},
    )
    r = detect(ds, ds.attrs)
    assert r is not None, (
        "case attr + ncol dim should still detect as EAMxx")
    assert r["primary"] == "EAMxx"


def test_source_attr_eamxx_still_strong_signal():
    """Regression: the explicit `source = E3SM Atmosphere Model
    (EAMxx)` signal is unambiguous and must stand alone, even
    without dim corroboration."""
    ds = xr.Dataset(
        {"foo": (("x",), np.zeros(3))},
        attrs={"source": "E3SM Atmosphere Model (EAMxx)"},
    )
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "EAMxx"


def test_normal_eamxx_file_still_detects():
    """Cycle-9 regression: the canonical EAMxx file shape with
    both source and ncol must keep detecting."""
    ds = xr.Dataset(
        {
            "T_mid": (("time", "ncol", "lev"),
                       np.zeros((1, 16, 8))),
            "ps": (("time", "ncol"), np.zeros((1, 16))),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
            "case": "F2010-SCREAMv1.run",
        },
    )
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "EAMxx"
    assert r["confidence"] == "high"

"""E3SM EAMxx (SCREAM) convention detection.

The cycle-6 dogfood `eamxx.nc` declares `Conventions = "CF-1.8"`
(so plain CF detection fires), but also ships rich identifying
attrs: `source = "E3SM Atmosphere Model (EAMxx)"`, `case` matching
SCREAM, and the dual-grid dim shape `(ncol, elem, gp)`.

Detection here must:
  - Identify EAMxx via the `source` or `case` attr.
  - Optionally corroborate via the dim shape (ncol AND/OR
    elem+gp+gp pattern).
  - Take precedence over plain CF when both fire (so the
    convention chain routes the file onto the unstructured
    branch rather than the rectilinear branch).
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.eamxx import detect


def _eamxx_dual_grid_dataset() -> xr.Dataset:
    """Synthetic stand-in for eamxx.nc — CF-1.8 attrs plus EAMxx
    identifying source/case attrs, plus dual-grid dim shape."""
    ds = xr.Dataset(
        {
            "T_mid": (
                ("time", "ncol", "lev"),
                np.zeros((1, 16, 8)),
                {"standard_name": "air_temperature", "units": "K"},
            ),
            "ps": (
                ("time", "ncol"),
                np.zeros((1, 16)),
                {"standard_name": "surface_air_pressure", "units": "Pa"},
            ),
            "v_dyn": (
                ("time", "elem", "gp", "gp", "lev"),
                np.zeros((1, 4, 4, 4, 8)),
            ),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
            "case": "ERP_Ln22.conusx4v1pg2_r05_oECv3.F2010-SCREAMv1-noAero",
            "institution_id": "E3SM-Project",
            "realm": "atmos",
        },
    )
    return ds


def test_eamxx_detected_from_source_attr():
    ds = _eamxx_dual_grid_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None, "EAMxx file with source attr must be detected"
    assert r["primary"] == "EAMxx"
    assert r["confidence"] == "high"
    assert any("source" in e.lower() for e in r["evidence"]), r["evidence"]


def test_eamxx_detected_from_case_attr_when_source_missing():
    """A SCREAM run where someone stripped `source` still has the
    `case` attr embedded in CIME naming convention; that alone is
    enough to flag EAMxx."""
    ds = _eamxx_dual_grid_dataset()
    attrs = dict(ds.attrs)
    del attrs["source"]
    ds.attrs = attrs
    r = detect(ds, attrs)
    assert r is not None, (
        "case attr containing SCREAM must still trigger EAMxx detection")
    assert r["primary"] == "EAMxx"
    assert any("case" in e.lower() for e in r["evidence"]), r["evidence"]


def test_eamxx_not_detected_on_plain_cf(cf_3d_file):
    """A plain CF file (no SCREAM/EAMxx attrs, no ncol/elem dims)
    must NOT be flagged — false positives would mis-route generic
    CF files onto the unstructured branch."""
    ds = xr.open_dataset(cf_3d_file)
    try:
        r = detect(ds, ds.attrs)
        assert r is None, (
            f"plain CF must not be EAMxx; got {r!r}")
    finally:
        ds.close()


def test_eamxx_dim_shape_recorded_in_evidence():
    """Evidence must record which axes were present (ncol /
    elem+gp) — downstream consumers route on this."""
    ds = _eamxx_dual_grid_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    ev = " ".join(r["evidence"]).lower()
    # The dual-grid case has both physics and dycore axes; one of
    # them must show up in evidence.
    assert "ncol" in ev or "elem" in ev or "gp" in ev, r["evidence"]


def test_eamxx_detected_with_only_ncol_physics_axis():
    """An EAMxx run that ships only the physics grid (no `elem`
    axis) — common for I/O-pruned restarts — must still detect."""
    ds = xr.Dataset(
        {
            "T_mid": (
                ("time", "ncol", "lev"),
                np.zeros((1, 16, 8)),
            ),
        },
        attrs={
            "Conventions": "CF-1.8",
            "source": "E3SM Atmosphere Model (EAMxx)",
        },
    )
    r = detect(ds, ds.attrs)
    assert r is not None
    assert r["primary"] == "EAMxx"


def test_eamxx_not_falsely_detected_on_wrf(wrf_file):
    ds = xr.open_dataset(wrf_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_eamxx_not_falsely_detected_on_roms(roms_file):
    ds = xr.open_dataset(roms_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()

"""CICE5/6 convention detection.

The cycle-6 dogfood `cice.nc` is a CICE restart file: no Conventions
attr, no `source`, no `model_name`, no `case` attr — the only signal
is the variable-name fingerprint (`aicen`, `vicen`, `Tsfcn`,
`iceumask`, etc.) on a `(ncat, nj, ni)` dim shape with a flattened
horizontal axis (nj=1, ni=N).

These tests pin the detection contract: identify CICE via the
variable-name fingerprint alone, reject look-alike files that
happen to share one or two of the names, and never falsely flag
generic CF / WRF / ROMS files.
"""
from __future__ import annotations

import numpy as np
import xarray as xr

from src.mcp.netcdf_reader.conventions.cice import detect


def _cice_restart_like_dataset(n_cells: int = 24) -> xr.Dataset:
    """Synthetic stand-in for cice.nc — flattened (nj=1, ni=N) with the
    classic CICE5/6 thermodynamic + dynamics variable suite. No global
    attrs (matches the real dogfood file)."""
    return xr.Dataset(
        {
            "aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "vicen": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "vsnon": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "Tsfcn": (("ncat", "nj", "ni"), np.zeros((1, 1, n_cells))),
            "uvel": (("nj", "ni"), np.zeros((1, n_cells))),
            "vvel": (("nj", "ni"), np.zeros((1, n_cells))),
            "iceumask": (("nj", "ni"), np.zeros((1, n_cells))),
            "stressp_1": (("nj", "ni"), np.zeros((1, n_cells))),
        }
    )


def test_cice_detected_from_variable_fingerprint():
    """No global attrs → detection has to lean entirely on the variable
    fingerprint. The classic suite (aicen, vicen, Tsfcn, iceumask,
    uvel, vvel, stressp_1) easily clears the ≥3-hit threshold."""
    ds = _cice_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None, "CICE restart file must be detected"
    assert r["primary"] == "CICE"
    assert r["confidence"] == "high"
    ev = " ".join(r["evidence"]).lower()
    assert "aicen" in ev or "vicen" in ev or "tsfcn" in ev, r["evidence"]


def test_cice_not_detected_with_too_few_fingerprint_vars():
    """A file that happens to ship `uvel` and `vvel` alone (2 hits
    of common-named velocity arrays) must NOT trigger CICE — those
    names are not unique enough on their own."""
    ds = xr.Dataset(
        {
            "uvel": (("y", "x"), np.zeros((4, 5))),
            "vvel": (("y", "x"), np.zeros((4, 5))),
        }
    )
    r = detect(ds, ds.attrs)
    assert r is None, f"2-hit weak file must not be CICE; got {r!r}"


def test_cice_evidence_lists_the_matched_fingerprint_vars():
    """The detector must explain itself — evidence should name which
    fingerprint vars matched so a user auditing the detection can
    verify the heuristic."""
    ds = _cice_restart_like_dataset()
    r = detect(ds, ds.attrs)
    assert r is not None
    # At least one evidence string should call out the fingerprint vars.
    assert any("fingerprint" in e.lower() or "aicen" in e or "vicen" in e
               for e in r["evidence"]), r["evidence"]


def test_cice_not_falsely_detected_on_generic_cf(cf_3d_file):
    ds = xr.open_dataset(cf_3d_file)
    try:
        r = detect(ds, ds.attrs)
        assert r is None, (
            f"detect() must return None for non-CICE files; got {r!r}")
    finally:
        ds.close()


def test_cice_not_falsely_detected_on_wrf(wrf_file):
    ds = xr.open_dataset(wrf_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_cice_not_falsely_detected_on_roms(roms_file):
    ds = xr.open_dataset(roms_file)
    try:
        assert detect(ds, ds.attrs) is None
    finally:
        ds.close()


def test_cice_3_hits_exactly_at_threshold():
    """Threshold check: exactly 3 fingerprint vars should still detect.
    This pins the threshold so a future tightening (e.g., 4) breaks the
    test rather than silently dropping coverage."""
    ds = xr.Dataset(
        {
            "aicen": (("ncat", "nj", "ni"), np.zeros((1, 1, 8))),
            "vicen": (("ncat", "nj", "ni"), np.zeros((1, 1, 8))),
            "Tsfcn": (("ncat", "nj", "ni"), np.zeros((1, 1, 8))),
        }
    )
    r = detect(ds, ds.attrs)
    assert r is not None, "exactly-3-hit file must still be detected"
    assert r["primary"] == "CICE"

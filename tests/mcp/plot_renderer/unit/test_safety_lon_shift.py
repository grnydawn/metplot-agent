# tests/mcp/plot_renderer/unit/test_safety_lon_shift.py
import numpy as np

from src.mcp.plot_renderer.safety import maybe_lon_shift


def test_no_convention_no_shift():
    values = np.arange(12).reshape(3, 4).astype("f4")
    lon = np.array([10.0, 20.0, 30.0, 40.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target=None)
    assert applied is False
    np.testing.assert_array_equal(out_v, values)
    np.testing.assert_array_equal(out_lon, lon)


def test_target_already_matches_no_shift():
    values = np.arange(8).reshape(2, 4).astype("f4")
    lon = np.array([-90.0, -45.0, 0.0, 45.0])  # already in -180..180
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="-180..180")
    assert applied is False


def test_shift_360_to_signed():
    # data is on 0..360 (e.g. lon=[180,270,0,90]); want -180..180
    values = np.array([[1.0, 2.0, 3.0, 4.0]])
    lon = np.array([180.0, 270.0, 0.0, 90.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="-180..180")
    assert applied is True
    assert out_lon.min() >= -180.0 and out_lon.max() <= 180.0
    # values must remain associated with their original lon labels:
    # original (180, 1.0), (270, 2.0), (0, 3.0), (90, 4.0)
    # post-shift: (-180, 1.0), (-90, 2.0), (0, 3.0), (90, 4.0) sorted ascending
    pairs = sorted(zip(out_lon.tolist(), out_v[0].tolist()))
    assert pairs == [(-180.0, 1.0), (-90.0, 2.0), (0.0, 3.0), (90.0, 4.0)]


def test_shift_signed_to_360():
    values = np.array([[1.0, 2.0, 3.0, 4.0]])
    lon = np.array([-90.0, 0.0, 90.0, 180.0])
    out_v, out_lon, applied = maybe_lon_shift(values, lon, target="0..360")
    assert applied is True
    pairs = sorted(zip(out_lon.tolist(), out_v[0].tolist()))
    # -90→270, 0→0, 90→90, 180→180
    assert pairs == [(0.0, 2.0), (90.0, 3.0), (180.0, 4.0), (270.0, 1.0)]

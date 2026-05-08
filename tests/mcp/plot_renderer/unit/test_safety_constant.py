# tests/mcp/plot_renderer/unit/test_safety_constant.py
import numpy as np

from src.mcp.plot_renderer.safety import (
    is_constant_field, percentile_clip_if_extreme,
)


def test_constant_true():
    arr = np.full((3, 3), 7.0)
    is_const, value = is_constant_field(arr)
    assert is_const is True
    assert value == 7.0


def test_constant_false():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    is_const, value = is_constant_field(arr)
    assert is_const is False
    assert value is None


def test_constant_nan_only():
    arr = np.array([[np.nan, np.nan]])
    is_const, value = is_constant_field(arr)
    # All-NaN counts as constant (no variation); but "value" is None.
    assert is_const is True
    assert value is None


def test_clip_no_op_for_normal_range():
    arr = np.array([[0.0, 1.0, 2.0, 3.0, 4.0]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr)
    # Range only 4 orders or less of magnitude → no clip.
    assert applied is False
    assert vmin == 0.0
    assert vmax == 4.0


def test_clip_triggers_for_extreme_outliers():
    # Median ~1.0, one cell at -9e36 (the classic missing-value sentinel).
    arr = np.array([[1.0, 1.0, 1.0, 1.0, -9.0e36]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr)
    assert applied is True
    # Clip uses 2/98 percentiles; these are above -9e36 and below max.
    assert vmin > -9.0e36
    assert vmin <= vmax


def test_clip_skips_with_explicit_vmin_vmax():
    arr = np.array([[1.0, 1.0, 1.0, 1.0, -9.0e36]])
    vmin, vmax, applied = percentile_clip_if_extreme(arr, vmin=0.0, vmax=2.0)
    assert applied is False
    assert vmin == 0.0
    assert vmax == 2.0

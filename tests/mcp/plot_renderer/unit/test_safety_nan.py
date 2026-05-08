# tests/mcp/plot_renderer/unit/test_safety_nan.py
import numpy as np

from src.mcp.plot_renderer.safety import nan_assessment


def test_no_nans():
    arr = np.array([[1.0, 2.0], [3.0, 4.0]])
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.0
    assert assess["all_nan"] is False
    assert assess["high_nan_fraction"] is False


def test_all_nan_flag():
    arr = np.full((3, 3), np.nan)
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 1.0
    assert assess["all_nan"] is True
    assert assess["high_nan_fraction"] is True


def test_high_nan_threshold_50pct():
    arr = np.array([[np.nan, np.nan, 1.0, 2.0]])  # 50%
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.5
    # Strictly > 0.5 trips the warning; exactly 0.5 does not.
    assert assess["high_nan_fraction"] is False


def test_high_nan_above_50():
    arr = np.array([[np.nan, np.nan, np.nan, 1.0]])  # 75%
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.75
    assert assess["high_nan_fraction"] is True


def test_nan_assessment_on_1d():
    arr = np.array([np.nan, 1.0, 2.0, np.nan])
    assess = nan_assessment(arr)
    assert assess["nan_fraction"] == 0.5

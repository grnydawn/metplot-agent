# tests/mcp/plot_renderer/unit/test_safety_downsample.py
import numpy as np

from src.mcp.plot_renderer.safety import (
    DOWNSAMPLE_2D_THRESHOLD, DOWNSAMPLE_1D_THRESHOLD,
    auto_downsample_2d, auto_downsample_1d,
)


def test_2d_below_threshold_unchanged():
    arr = np.zeros((100, 100), dtype="f4")
    coords = {"lat": np.arange(100, dtype="f8"),
              "lon": np.arange(100, dtype="f8")}
    out, out_coords, action = auto_downsample_2d(arr, coords, enabled=True)
    assert out.shape == (100, 100)
    assert action is None


def test_2d_above_threshold_downsamples():
    # 4M cells exactly at threshold → no action; one above → action.
    n = 2049
    arr = np.zeros((n, n), dtype="f4")
    coords = {"lat": np.arange(n, dtype="f8"),
              "lon": np.arange(n, dtype="f8")}
    out, out_coords, action = auto_downsample_2d(arr, coords, enabled=True)
    assert out.shape[0] * out.shape[1] <= DOWNSAMPLE_2D_THRESHOLD
    assert action is not None
    assert action["from_shape"] == (n, n)
    assert action["to_shape"] == out.shape
    assert action["factor"]["lat"] >= 2
    assert out_coords["lat"].shape[0] == out.shape[0]


def test_2d_disabled_returns_full_array():
    n = 2049
    arr = np.zeros((n, n), dtype="f4")
    coords = {"lat": np.arange(n, dtype="f8"),
              "lon": np.arange(n, dtype="f8")}
    out, _, action = auto_downsample_2d(arr, coords, enabled=False)
    assert out.shape == (n, n)
    assert action is None


def test_1d_below_threshold_unchanged():
    arr = np.zeros(50_000, dtype="f4")
    axis = np.arange(50_000)
    out, out_axis, action = auto_downsample_1d(arr, axis, enabled=True)
    assert out.shape[0] == 50_000
    assert action is None


def test_1d_above_threshold_decimates():
    n = DOWNSAMPLE_1D_THRESHOLD + 1
    arr = np.arange(n, dtype="f4")
    axis = np.arange(n)
    out, out_axis, action = auto_downsample_1d(arr, axis, enabled=True)
    assert out.shape[0] <= DOWNSAMPLE_1D_THRESHOLD
    assert action is not None
    assert action["from_shape"] == (n,)


def test_2d_disabled_with_huge_returns_full():
    arr = np.zeros((3000, 3000), dtype="f4")
    coords = {"lat": np.arange(3000, dtype="f8"),
              "lon": np.arange(3000, dtype="f8")}
    out, _, action = auto_downsample_2d(arr, coords, enabled=False)
    assert action is None
    assert out.shape == (3000, 3000)

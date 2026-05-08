# src/mcp/plot_renderer/safety.py
"""⤴ format-agnostic — eligible for _core/ lift.

Robustness behaviors for the renderer (spec §7). The safety pass runs
on already-normalized numpy arrays AFTER style resolution and BEFORE
the matplotlib drawing call.
"""
from __future__ import annotations

from math import ceil
from typing import Any

import numpy as np


DOWNSAMPLE_2D_THRESHOLD = 4_000_000   # cells (e.g. 2048 × 2048)
DOWNSAMPLE_1D_THRESHOLD = 100_000     # points


def _coarsen_factor(n: int, target: int) -> int:
    """Smallest k >= 1 such that n // k <= target."""
    if n <= target:
        return 1
    return int(ceil(n / target))


def auto_downsample_2d(
    values: np.ndarray, coords: dict[str, np.ndarray], *, enabled: bool,
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any] | None]:
    """Downsample 2D array via per-axis coarsening if total cells exceed
    threshold and `enabled` is True. Returns (values, coords, action) where
    action is None when no downsample happened.
    """
    if not enabled:
        return values, coords, None
    n_lat, n_lon = values.shape
    if n_lat * n_lon <= DOWNSAMPLE_2D_THRESHOLD:
        return values, coords, None
    # Compute per-axis factor proportional to a sqrt-balance toward the cap.
    target_each = int(DOWNSAMPLE_2D_THRESHOLD ** 0.5)
    k_lat = _coarsen_factor(n_lat, target_each)
    k_lon = _coarsen_factor(n_lon, target_each)
    # Trim to multiples of the factor so reshape is clean.
    n_lat_trim = (n_lat // k_lat) * k_lat
    n_lon_trim = (n_lon // k_lon) * k_lon
    arr = values[:n_lat_trim, :n_lon_trim].reshape(
        n_lat_trim // k_lat, k_lat, n_lon_trim // k_lon, k_lon,
    ).mean(axis=(1, 3))
    new_coords = {
        "lat": coords["lat"][:n_lat_trim].reshape(-1, k_lat).mean(axis=1),
        "lon": coords["lon"][:n_lon_trim].reshape(-1, k_lon).mean(axis=1),
    }
    return arr, new_coords, {
        "from_shape": (n_lat, n_lon),
        "to_shape": arr.shape,
        "factor": {"lat": k_lat, "lon": k_lon},
    }


def auto_downsample_1d(
    values: np.ndarray, axis: np.ndarray, *, enabled: bool,
) -> tuple[np.ndarray, np.ndarray, dict[str, Any] | None]:
    """Stride-decimate a 1D array if length exceeds threshold."""
    if not enabled:
        return values, axis, None
    n = values.shape[0]
    if n <= DOWNSAMPLE_1D_THRESHOLD:
        return values, axis, None
    k = _coarsen_factor(n, DOWNSAMPLE_1D_THRESHOLD)
    return (values[::k], axis[::k],
            {"from_shape": (n,), "to_shape": (values[::k].shape[0],),
             "factor": {"axis": k}})


def nan_assessment(values: np.ndarray) -> dict[str, Any]:
    """Compute NaN statistics. Threshold for `high_nan_fraction` is > 0.5."""
    total = values.size
    if total == 0:
        return {"nan_fraction": 0.0, "all_nan": False,
                "high_nan_fraction": False}
    n_nan = int(np.isnan(values).sum())
    frac = n_nan / total
    return {
        "nan_fraction": frac,
        "all_nan": (n_nan == total),
        "high_nan_fraction": (frac > 0.5),
    }

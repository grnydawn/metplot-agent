"""format-agnostic — eligible for _core/ lift.

Spec -> typed numpy arrays. Decodes the inline JSON form (NaN strings,
nested lists, ISO time strings) and (in Task 9) dispatches the
slice_ref form to slice_loader. Renderer-side modules consume only
the outputs of this module — they never see the raw spec dict.
"""
from __future__ import annotations

from typing import Any

import numpy as np


class InvalidSpecError(ValueError):
    pass


def _decode_nans(values: Any) -> np.ndarray:
    """Convert nested lists with possible string 'NaN' into a float array."""
    arr = np.asarray(values, dtype=object)
    flat = arr.reshape(-1)
    out = np.empty(flat.shape, dtype="float64")
    for i, v in enumerate(flat):
        if isinstance(v, str) and v == "NaN":
            out[i] = np.nan
        else:
            out[i] = float(v)
    return out.reshape(arr.shape)


def _decode_axis(values: Any, axis_name: str) -> np.ndarray:
    """Decode an axis (lat/lon = float, time = datetime64, vertical = float)."""
    if axis_name == "time":
        # Strings -> datetime64; pass-throughs already datetime stay
        return np.array(values, dtype="datetime64[ns]")
    return np.asarray(values, dtype="float64")


def normalize_2d(spec: dict[str, Any]) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Normalize a render_map inline spec.

    Returns (values, coords, meta). values shape is (n_lat, n_lon).
    """
    if "values" not in spec:
        raise InvalidSpecError("missing required field: values")
    if "lat" not in spec:
        raise InvalidSpecError("missing required field: lat")
    if "lon" not in spec:
        raise InvalidSpecError("missing required field: lon")
    values = _decode_nans(spec["values"])
    lat = _decode_axis(spec["lat"], "lat")
    lon = _decode_axis(spec["lon"], "lon")
    if values.ndim != 2:
        raise InvalidSpecError(
            f"render_map values must be 2D, got shape {values.shape}")
    meta = {k: spec[k] for k in ("units", "long_name", "standard_name",
                                  "variable", "lon_convention")
            if k in spec}
    return values, {"lat": lat, "lon": lon}, meta


def normalize_1d_series(
    spec: dict[str, Any], *, axis_name: str,
) -> list[dict[str, Any]]:
    """Normalize render_timeseries / render_profile spec into a series list.

    axis_name is "time" for timeseries, "vertical" for profile.
    """
    has_series = "series" in spec and spec["series"] is not None
    has_sugar = "values" in spec and axis_name in spec
    if has_series and has_sugar:
        raise InvalidSpecError(
            "series_and_sugar_both_set: supply either `series` or "
            f"`values+{axis_name}`, not both")
    if not has_series and not has_sugar:
        raise InvalidSpecError(
            f"missing required data: provide `series` or `values+{axis_name}`")

    raw_series: list[dict[str, Any]]
    if has_series:
        raw_series = list(spec["series"])
    else:
        raw_series = [{"values": spec["values"], axis_name: spec[axis_name],
                       "label": spec.get("label")}]

    out: list[dict[str, Any]] = []
    for i, s in enumerate(raw_series):
        if "values" not in s:
            raise InvalidSpecError(f"series[{i}] missing values")
        if axis_name not in s:
            raise InvalidSpecError(f"series[{i}] missing {axis_name}")
        values = _decode_nans(s["values"])
        axis = _decode_axis(s[axis_name], axis_name)
        if values.ndim != 1:
            raise InvalidSpecError(
                f"series[{i}] values must be 1D, got shape {values.shape}")
        if axis.shape != values.shape:
            raise InvalidSpecError(
                f"series[{i}] {axis_name} length {axis.shape[0]} != values "
                f"length {values.shape[0]}")
        out.append({
            "values": values,
            "axis":   axis,
            "label":  s.get("label") or f"series_{i}",
            "color":  s.get("color"),
        })
    return out


def normalize_2d_any_form(
    spec: dict[str, Any],
) -> tuple[np.ndarray, dict[str, np.ndarray], dict[str, Any]]:
    """Dispatch on inline vs slice_ref form for render_map specs."""
    has_inline = "values" in spec
    has_slice_ref = spec.get("slice_ref") is not None
    if has_inline and has_slice_ref:
        raise InvalidSpecError(
            "supply either inline values or slice_ref, not both")
    if not has_inline and not has_slice_ref:
        raise InvalidSpecError("missing data: provide values+lat+lon or slice_ref")
    if has_inline:
        return normalize_2d(spec)
    # slice_ref path
    from src.mcp.plot_renderer.slice_loader import (
        NetCDFSliceLoader, SliceFileUnreadable,
    )
    try:
        da = NetCDFSliceLoader().load(spec["slice_ref"])
    except SliceFileUnreadable as e:
        raise InvalidSpecError(f"slice_ref unreadable: {e}") from e
    # Squeeze leading singleton dims (e.g., time=1)
    da = da.squeeze(drop=True)
    if da.ndim != 2:
        raise InvalidSpecError(
            f"slice_ref variable must reduce to 2D for render_map; got {da.ndim}D")
    # Try to find lat/lon coord names; fall back to dim names.
    dim_lat, dim_lon = da.dims
    coords = {
        "lat": np.asarray(da[dim_lat].values, dtype="float64"),
        "lon": np.asarray(da[dim_lon].values, dtype="float64"),
    }
    values = np.asarray(da.values, dtype="float64")
    meta: dict[str, Any] = {
        k: da.attrs[k] for k in ("units", "long_name", "standard_name")
        if k in da.attrs
    }
    if "variable" in spec.get("slice_ref", {}):
        meta["variable"] = spec["slice_ref"]["variable"]
    if spec.get("lon_convention") is not None:
        meta["lon_convention"] = spec["lon_convention"]
    return values, coords, meta

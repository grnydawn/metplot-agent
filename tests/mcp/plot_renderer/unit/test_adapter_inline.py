# tests/mcp/plot_renderer/unit/test_adapter_inline.py
import math

import numpy as np

from src.mcp.plot_renderer.adapter import (
    InvalidSpecError, normalize_2d, normalize_1d_series,
)


def test_inline_2d_basic():
    spec = {
        "values": [[1.0, 2.0], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [10.0, 20.0],
        "units": "K",
    }
    arr, coords, meta = normalize_2d(spec)
    assert arr.shape == (2, 2)
    assert arr.dtype.kind == "f"
    assert list(coords["lat"]) == [0.0, 1.0]
    assert list(coords["lon"]) == [10.0, 20.0]
    assert meta["units"] == "K"


def test_inline_2d_decodes_nan_string():
    spec = {
        "values": [[1.0, "NaN"], [3.0, 4.0]],
        "lat": [0.0, 1.0],
        "lon": [10.0, 20.0],
    }
    arr, _, _ = normalize_2d(spec)
    assert math.isnan(arr[0, 1])
    assert arr[1, 0] == 3.0


def test_inline_2d_missing_lat_errors():
    spec = {"values": [[1.0]], "lon": [0.0]}
    try:
        normalize_2d(spec)
    except InvalidSpecError as e:
        assert "lat" in str(e)
        return
    raise AssertionError("expected InvalidSpecError")


def test_inline_1d_series_single_sugar():
    spec = {"values": [1.0, 2.0, 3.0],
            "time": ["2024-01", "2024-02", "2024-03"],
            "label": "demo"}
    series = normalize_1d_series(spec, axis_name="time")
    assert len(series) == 1
    assert series[0]["label"] == "demo"
    assert list(series[0]["values"]) == [1.0, 2.0, 3.0]
    # ISO strings parsed to datetime64
    assert np.issubdtype(series[0]["axis"].dtype, np.datetime64)


def test_inline_1d_series_multi():
    spec = {"series": [
        {"values": [1.0], "time": ["2024-01"], "label": "A"},
        {"values": [2.0], "time": ["2024-01"], "label": "B"},
    ]}
    series = normalize_1d_series(spec, axis_name="time")
    assert [s["label"] for s in series] == ["A", "B"]


def test_inline_1d_series_both_set_errors():
    spec = {"values": [1.0], "time": ["2024-01"],
            "series": [{"values": [2.0], "time": ["2024-01"]}]}
    try:
        normalize_1d_series(spec, axis_name="time")
    except InvalidSpecError as e:
        assert "series_and_sugar_both_set" in str(e)
        return
    raise AssertionError("expected InvalidSpecError")


def test_inline_1d_series_profile_axis():
    spec = {"values": [288.0, 250.0],
            "vertical": [1000.0, 500.0],
            "vertical_units": "hPa", "label": "demo"}
    series = normalize_1d_series(spec, axis_name="vertical")
    assert len(series) == 1
    assert list(series[0]["axis"]) == [1000.0, 500.0]

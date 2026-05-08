# tests/mcp/plot_renderer/unit/test_oracle_schema.py
import matplotlib.pyplot as plt
import pytest

from src.mcp.plot_renderer.oracle import (
    ORACLE_SCHEMA_VERSION, REQUIRED_TOP_LEVEL_FIELDS,
    OracleIncomplete, capture_common,
)


def test_schema_version_pinned():
    assert ORACLE_SCHEMA_VERSION == 1


def test_required_top_level_fields():
    expected = {"oracle_schema_version", "tool", "output", "data",
                "style_resolution", "drawn", "style_template_applied"}
    assert REQUIRED_TOP_LEVEL_FIELDS == expected


def test_capture_common_minimal():
    fig = plt.figure(figsize=(4, 3))
    plt.plot([0, 1], [0, 1])
    oracle = capture_common(
        fig=fig,
        tool="render_timeseries",
        resolved_spec={"colormap": "viridis", "dpi": 150,
                       "format": "png", "aspect": "auto",
                       "font_scale": 1.0, "colorbar_position": "none",
                       "gridlines": "light"},
        style_resolution_sources={
            "colormap": "library_default",
            "colorbar_position": "explicit",
            "gridlines": "library_default",
            "font_scale": "library_default",
            "aspect": "library_default",
        },
        safety_actions={
            "applied_downsample": None,
            "applied_lon_shift": None,
            "applied_clip_pct": None,
            "vmin_used": 0.0, "vmax_used": 1.0,
            "nan_fraction": 0.0,
        },
        output_path="/tmp/x.png",
        output_size_bytes=12345,
        data_shape=[2],
    )
    plt.close(fig)
    assert oracle["oracle_schema_version"] == 1
    assert oracle["tool"] == "render_timeseries"
    assert oracle["output"]["path"] == "/tmp/x.png"
    assert oracle["output"]["format"] == "png"
    assert oracle["output"]["dpi"] == 150
    assert oracle["data"]["shape"] == [2]
    assert oracle["style_resolution"]["colormap"]["source"] == "library_default"


def test_oracle_incomplete_when_missing_required():
    fig = plt.figure()
    with pytest.raises(OracleIncomplete):
        capture_common(
            fig=fig, tool="render_map",
            resolved_spec={},  # missing several presentation fields
            style_resolution_sources={},  # incomplete
            safety_actions={},
            output_path="/tmp/x.png",
            output_size_bytes=1, data_shape=[1, 1],
        )
    plt.close(fig)

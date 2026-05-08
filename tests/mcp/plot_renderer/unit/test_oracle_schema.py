# tests/mcp/plot_renderer/unit/test_oracle_schema.py
import matplotlib.pyplot as plt
import pytest

from src.mcp.plot_renderer.oracle import (
    ORACLE_SCHEMA_VERSION, REQUIRED_TOP_LEVEL_FIELDS,
    OracleIncomplete, capture_common,
    drawn_for_timeseries, drawn_for_profile,
    style_template_applied_block, finalize,
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


def test_drawn_for_timeseries():
    fig, ax = plt.subplots()
    ax.set_title("Annual mean")
    ax.set_xlabel("Year")
    ax.set_ylabel("°C")
    ax.plot([0, 1], [0, 1], label="A", color="C0", linestyle="-")
    ax.legend()
    drawn = drawn_for_timeseries(
        fig=fig, ax=ax,
        series_meta=[{"label": "A", "n_points": 2,
                       "color": "C0", "linestyle": "-"}],
        trendline_kind=None,
    )
    plt.close(fig)
    assert drawn["title"] == "Annual mean"
    assert drawn["axis_labels"]["x"] == "Year"
    assert drawn["axis_labels"]["y"] == "°C"
    assert drawn["legend_present"] is True
    assert drawn["series_count"] == 1
    assert drawn["series"][0]["label"] == "A"
    assert drawn["trendline_present"] is False


def test_drawn_for_profile_log_scale_invert():
    fig, ax = plt.subplots()
    ax.set_yscale("log")
    ax.invert_yaxis()
    ax.plot([280.0, 220.0], [1000.0, 100.0], label="P", color="C1")
    drawn = drawn_for_profile(
        fig=fig, ax=ax, vertical_axis="y",
        series_meta=[{"label": "P", "n_points": 2,
                       "color": "C1", "linestyle": "-"}],
    )
    plt.close(fig)
    assert drawn["log_scale"] is True
    assert drawn["invert_pressure"] is True
    assert drawn["vertical_axis"] == "y"


def test_style_template_applied_block_with_template():
    block = style_template_applied_block(
        template={"colormap_kind": "diverging",
                  "source": {"image_path": "x.png",
                              "extracted_by": "claude",
                              "extracted_at": "2026-05-07T00:00:00Z",
                              "confidence": 0.9}},
        trace={"fields_applied": ["colormap_kind"], "fields_ignored": []},
    )
    assert block is not None
    assert "colormap_kind" in block["fields_applied"]
    assert block["source"]["image_path"] == "x.png"


def test_style_template_applied_block_with_none_template():
    assert style_template_applied_block(template=None, trace={"fields_applied": [], "fields_ignored": []}) is None


def test_finalize_passes_when_all_required_present():
    oracle = {
        "oracle_schema_version": 1, "tool": "render_map",
        "output": {}, "data": {}, "style_resolution": {},
        "drawn": {"title": None}, "style_template_applied": None,
    }
    out = finalize(oracle)
    assert out is oracle

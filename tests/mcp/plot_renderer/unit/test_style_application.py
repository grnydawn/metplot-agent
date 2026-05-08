# tests/mcp/plot_renderer/unit/test_style_application.py
from src.mcp.plot_renderer.style import apply, _MAPPING


def test_colormap_name_direct():
    spec = {}
    template = {"colormap_name": "RdYlBu_r"}
    resolved, trace = apply(spec, template)
    assert resolved["colormap"] == "RdYlBu_r"
    assert "colormap_name" in trace["fields_applied"]


def test_colormap_kind_sequential():
    resolved, trace = apply({}, {"colormap_kind": "sequential"})
    assert resolved["colormap"] == "viridis"
    assert "colormap_kind" in trace["fields_applied"]


def test_colormap_kind_diverging_sets_vcenter():
    resolved, trace = apply({}, {"colormap_kind": "diverging"})
    assert resolved["colormap"] == "RdBu_r"
    assert resolved["vcenter"] == 0.0


def test_colormap_kind_categorical():
    resolved, _ = apply({}, {"colormap_kind": "categorical"})
    assert resolved["colormap"] == "tab10"


def test_explicit_colormap_beats_template():
    resolved, trace = apply(
        {"colormap": "magma"},
        {"colormap_kind": "diverging"},
    )
    assert resolved["colormap"] == "magma"
    assert any(f["field"] == "colormap_kind" and
               f["reason"] == "overridden_by_explicit_spec"
               for f in trace["fields_ignored"])


def test_colormap_name_takes_precedence_over_kind_in_template():
    resolved, _ = apply({}, {"colormap_name": "plasma",
                              "colormap_kind": "sequential"})
    assert resolved["colormap"] == "plasma"


def test_clip_pct_passthrough():
    resolved, _ = apply({}, {"clip_pct": [5.0, 95.0]})
    assert resolved["clip_pct"] == [5.0, 95.0]


def test_vcenter_passthrough():
    resolved, _ = apply({}, {"vcenter": 0.5})
    assert resolved["vcenter"] == 0.5


def test_mapping_table_has_all_template_keys():
    expected = {
        "colormap_name", "colormap_kind", "vcenter", "clip_pct",
    }
    for k in expected:
        assert k in _MAPPING


def test_projection_family_robinson():
    resolved, _ = apply({}, {"projection_family": "robinson"})
    assert resolved["projection"] == "Robinson"


def test_projection_family_polar_north():
    resolved, _ = apply({}, {"projection_family": "polar_stereo_north"})
    assert resolved["projection"] == "NorthPolarStereo"


def test_projection_family_unknown_ignored():
    resolved, trace = apply({}, {"projection_family": "weird"})
    assert "projection" not in resolved
    assert any(f["field"] == "projection_family" for f in trace["fields_ignored"])


def test_layout_fields():
    resolved, _ = apply({}, {
        "colorbar_position": "bottom",
        "legend_placement": "outside_right",
        "gridlines": "heavy",
        "aspect": 1.5,
    })
    assert resolved["colorbar_position"] == "bottom"
    assert resolved["legend_placement"] == "outside_right"
    assert resolved["gridlines"] == "heavy"
    assert resolved["aspect"] == 1.5


def test_font_scale_clamped():
    # Below range
    resolved, _ = apply({}, {"font_scale": 0.3})
    assert resolved["font_scale"] == 0.7
    # Above range
    resolved, _ = apply({}, {"font_scale": 2.0})
    assert resolved["font_scale"] == 1.5


def test_advisory_fields_passthrough():
    resolved, _ = apply({}, {
        "extent_hint": "global",
        "title_placement": "top",
        "label_density": "verbose",
    })
    assert resolved.get("_advisory_extent_hint") == "global"
    assert resolved.get("_advisory_title_placement") == "top"
    assert resolved.get("_advisory_label_density") == "verbose"

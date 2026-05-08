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

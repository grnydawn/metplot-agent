# tests/mcp/plot_renderer/unit/test_style_template_unknown.py
from src.mcp.plot_renderer.style import apply, source_provenance


def test_unknown_field_recorded():
    resolved, trace = apply({}, {"warp_speed": "9001"})
    assert any(f["field"] == "warp_speed" and
               f["reason"] == "unknown_template_field"
               for f in trace["fields_ignored"])


def test_empty_template_is_noop():
    resolved, trace = apply({"existing": "yes"}, {})
    assert resolved == {"existing": "yes"}
    assert trace["fields_applied"] == []
    assert trace["fields_ignored"] == []


def test_none_template_is_noop():
    resolved, trace = apply({"a": 1}, None)
    assert resolved == {"a": 1}
    assert trace["fields_applied"] == []


def test_source_provenance_extracted():
    template = {
        "colormap_kind": "sequential",
        "source": {
            "image_path": "/data/ref.png",
            "extracted_by": "claude-opus-4-7",
            "extracted_at": "2026-05-07T12:00:00Z",
            "confidence": 0.85,
        },
    }
    src = source_provenance(template)
    assert src is not None
    assert src["image_path"] == "/data/ref.png"
    assert src["confidence"] == 0.85


def test_source_provenance_missing_returns_none():
    assert source_provenance({"colormap_kind": "sequential"}) is None
    assert source_provenance(None) is None

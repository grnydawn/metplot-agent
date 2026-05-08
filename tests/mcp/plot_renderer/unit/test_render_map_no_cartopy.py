from src.mcp.plot_renderer.tools import render_map as rm


def test_cartopy_missing_returns_ambiguity_envelope(monkeypatch):
    monkeypatch.setattr(rm, "_CARTOPY_OK", False)
    monkeypatch.setattr(rm, "_CARTOPY_IMPORT_ERROR", "no module 'cartopy'")
    spec = {"values": [[1.0, 2.0], [3.0, 4.0]],
            "lat": [0.0, 1.0], "lon": [0.0, 1.0]}
    env = rm.render_map(spec)
    assert env["ok"] is False
    assert env["error"]["code"] == "ambiguous"
    assert env["error"]["subcode"] == "cartopy_missing"
    assert any("cartopy" in c["value"]
               for c in env["error"]["candidates"])
